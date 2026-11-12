"""Source-free explorer contract, deterministic exports, and binary co-occurrence.

This module never writes canonical inputs or refreshes reference outputs.
Offsets are zero-based, half-open Unicode codepoints within canonical paragraphs.
"""
from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import re
from collections import Counter, defaultdict
from datetime import date
import xml.etree.ElementTree as ET
import zipfile

SCHEMA = "pkoc-explorer-v1"
ROOT = Path(__file__).resolve().parents[1]
SCALES = ("sentence", "paragraph", "report")
ARRAYS = ("reports", "nodes", "occurrences", "claims", "attributes", "paragraphs",
          "sentences", "interventions", "correspondence", "reference_units", "networks", "codebook")
FORBIDDEN = {"text", "paragraph_text", "source_text", "raw_text", "raw_request", "raw_response",
             "request_body", "response_body", "journal", "api_key", "authorization", "model_path",
             "snapshot_path", "reason", "note"}
PRIVATE = re.compile(r"(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/(?:Users|home)/|\\\\[^\\]+\\|-----BEGIN .*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def _array(value):
    """Normalize historical scalar/list fields without splitting singleton strings."""
    return [] if value is None else value if isinstance(value, list) else [value]


def _strings(value, label):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(f"{label} must be a list of nonempty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} contains duplicates")
    return value


def _int(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _unique(rows, keys, label):
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{label} rows must be objects")
        key = tuple(row.get(k) for k in keys)
        if any(not isinstance(k, str) or not k for k in key) or key in result:
            raise ValueError(f"{label} has missing or duplicate identifier {key}")
        result[key] = row
    return result


def _public(value, path="bundle"):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in FORBIDDEN:
                raise ValueError(f"Unreviewed/private field {path}.{key}")
            _public(item, f"{path}.{key}")
    elif isinstance(value, list):
        for item in value:
            _public(item, path)
    elif isinstance(value, str) and PRIVATE.search(value):
        raise ValueError(f"Private path or credential marker in {path}")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Nonfinite number in {path}")


def validate_bundle(bundle):
    """Reject malformed or source-bearing bundles before projection/export."""
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    if set(bundle) - {"schema", "dataset", "provenance", *ARRAYS}:
        raise ValueError("Unknown bundle root fields")
    for key in ARRAYS:
        if not isinstance(bundle.get(key), list):
            raise ValueError(f"{key} must be an array")
    dataset = bundle.get("dataset", {})
    if not isinstance(dataset, dict) or not isinstance(dataset.get("id"), str) or not dataset["id"]:
        raise ValueError("dataset requires an id")
    if not isinstance(bundle.get("provenance"), dict):
        raise ValueError("provenance must be an object")
    rosters = _strings(dataset.get("rosters"), "dataset.rosters")
    if not rosters or set(rosters) - {"L", "A", "R"}:
        raise ValueError("Unsupported workflow")
    if dataset.get("kind") not in ("frozen-study", "model-only"):
        raise ValueError("dataset.kind must be frozen-study or model-only")
    if dataset["kind"] == "model-only" and rosters != ["L"]:
        raise ValueError("Automated cases can expose only the L branch")
    reports = _unique(bundle["reports"], ["report_id"], "reports")
    for row in reports.values():
        year = row.get("year")
        if year is not None and (type(year) is not int or not 1000 <= year <= 9999):
            raise ValueError("Report year must be a year integer or null")
        publication_date = row.get("report_date")
        if publication_date is not None and (not isinstance(publication_date, str) or not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", publication_date)):
            raise ValueError("Date must preserve available ISO precision")
        if publication_date is not None:
            parts = [int(part) for part in publication_date.split("-")]
            date(*(parts + [1] * (3 - len(parts))))
        if publication_date is not None and year is not None and int(publication_date[:4]) != year:
            raise ValueError("Report year/date mismatch")
        if row.get("official_url") and not row["official_url"].startswith("https://"):
            raise ValueError("Official source URLs must use HTTPS")
    nodes = _unique(bundle["nodes"], ["workflow", "actor_id"], "nodes")
    for (workflow, _), row in nodes.items():
        if workflow not in rosters or not isinstance(row.get("name"), str):
            raise ValueError("Node has unknown workflow or invalid name")
        for key in ("aliases", "cameo_codes", "primary_cameo_codes"):
            _strings(row.get(key, []), f"node.{key}")
        if "layout" in row:
            if not all(type(row["layout"].get(k)) in (int, float) and math.isfinite(row["layout"][k]) for k in ("x", "y")):
                raise ValueError("Node layout requires finite x/y")
    paragraphs = _unique(bundle["paragraphs"], ["paragraph_id"], "paragraphs")
    for row in paragraphs.values():
        if (row.get("report_id"),) not in reports or not re.fullmatch("[0-9a-f]{64}", row.get("text_sha256", "")):
            raise ValueError("Paragraph requires a report and SHA-256")
    sentences = _unique(bundle["sentences"], ["sentence_id"], "sentences")
    for row in sentences.values():
        para = paragraphs.get((row.get("paragraph_id"),))
        if not para or para["report_id"] != row.get("report_id"):
            raise ValueError("Sentence has mismatched paragraph/report")
        if _int(row.get("end"), "sentence.end") <= _int(row.get("start"), "sentence.start"):
            raise ValueError("Sentence span must be nonempty")
    occurrences = _unique(bundle["occurrences"], ["workflow", "occurrence_id"], "occurrences")
    for (workflow, _), row in occurrences.items():
        if workflow not in rosters:
            raise ValueError("Occurrence workflow is unavailable")
        actor = row.get("actor_id")
        if actor is not None and (workflow, actor) not in nodes:
            raise ValueError("Occurrence references unknown actor")
        para = paragraphs.get((row.get("paragraph_id"),))
        if not para or para["report_id"] != row.get("report_id"):
            raise ValueError("Occurrence has mismatched paragraph/report")
        if not isinstance(row.get("surface"), str) or not isinstance(row.get("grounding_status"), str) or not row["grounding_status"]:
            raise ValueError("Occurrence requires surface and grounding status strings")
        start, end = row.get("start"), row.get("end")
        if (start is None) != (end is None):
            raise ValueError("Occurrence offsets must be both null or both integers")
        if start is not None:
            if _int(end, "occurrence.end") <= _int(start, "occurrence.start"):
                raise ValueError("Occurrence span must be nonempty")
            if row.get("grounding_status") == "grounded" and len(row.get("surface", "")) != end - start:
                raise ValueError("Grounded surface length disagrees with codepoint offsets")
        if row.get("sentence_id") is not None:
            sentence = sentences.get((row["sentence_id"],))
            if not sentence or sentence["paragraph_id"] != row["paragraph_id"]:
                raise ValueError("Occurrence has mismatched sentence")
            if start is not None and not sentence["start"] <= start < end <= sentence["end"]:
                raise ValueError("Occurrence extends beyond its sentence")
    for array, keys in (("claims", ["workflow", "actor_id", "claim_key"]),
                        ("attributes", ["workflow", "actor_id", "report_id"])):
        for row in _unique(bundle[array], keys, array).values():
            if (row["workflow"], row["actor_id"]) not in nodes:
                raise ValueError(f"{array} references unknown actor")
            if array == "attributes" and (row["report_id"],) not in reports:
                raise ValueError("Attribute references unknown report")
            for key in ("role_codes", "specialty_codes", "cameo_codes"):
                _strings(row.get(key, []), f"{array}.{key}")
            if array == "attributes":
                _strings(row.get("primary_cameo_codes", []), "attributes.primary_cameo_codes")
    _strings(bundle["reference_units"], "reference_units")
    if any((pid,) not in paragraphs for pid in bundle["reference_units"]):
        raise ValueError("Reference paragraph is unavailable")
    for graph in bundle["networks"]:
        if graph.get("workflow") not in rosters or graph.get("scale") not in SCALES:
            raise ValueError("Invalid network workflow/scale")
        _strings(graph.get("report_ids"), "network.report_ids")
        if type(graph.get("reference_only")) is not bool:
            raise ValueError("Network reference_only must be boolean")
        graph_nodes = _unique(graph.get("nodes", []), ["actor_id"], "network nodes")
        seen = set()
        for edge in graph.get("edges", []):
            pair = tuple(sorted((edge.get("source", ""), edge.get("target", ""))))
            if pair[0] == pair[1] or pair in seen or any((aid,) not in graph_nodes for aid in pair):
                raise ValueError("Network has duplicate, self, or unknown edge")
            seen.add(pair)
            _strings(edge.get("unit_ids"), "edge.unit_ids")
            if _int(edge.get("weight"), "edge.weight", 1) != len(edge["unit_ids"]):
                raise ValueError("Edge weight must count distinct units")
    for graph in bundle["networks"]:
        expected = project_network(bundle, graph["workflow"], graph["scale"], graph.get("report_ids"), graph.get("reference_only", False))
        for key in ("edges", "incidences", "summary", "exclusions"):
            if graph.get(key) != expected[key]:
                raise ValueError(f"Embedded network {key} disagrees with projection")
        measured = {row["actor_id"]: (row["degree"], row["strength"]) for row in expected["nodes"]}
        supplied = {row["actor_id"]: (row.get("degree"), row.get("strength")) for row in graph["nodes"]}
        if supplied != measured:
            raise ValueError("Embedded network drops isolates or changes degree/strength")
    _public(bundle)
    return {"schema": SCHEMA, "reports": len(reports), "nodes": len(nodes), "occurrences": len(occurrences),
            "paragraphs": len(paragraphs), "sentences": len(sentences)}


def project_network(bundle, workflow, scale, report_ids=None, reference_only=False):
    """Project binary unit incidences, retaining the complete workflow roster."""
    if workflow not in bundle["dataset"]["rosters"] or scale not in SCALES:
        raise ValueError("Unknown workflow or scale")
    available = {row["report_id"] for row in bundle["reports"]}
    selected = available if report_ids is None else set(_strings(list(report_ids), "report_ids"))
    if selected - available:
        raise ValueError("Unknown selected report")
    reference_only = bool(reference_only or workflow == "R")
    reference = set(bundle["reference_units"])
    roster = sorted((row for row in bundle["nodes"] if row["workflow"] == workflow), key=lambda x: x["actor_id"])
    actor_ids = {row["actor_id"] for row in roster}
    units, unit_reports = defaultdict(set), {}
    exclusions = {"unassigned_identity": 0, "missing_unit": 0, "outside_selection": 0}
    for row in bundle["occurrences"]:
        if row["workflow"] != workflow:
            continue
        if row["report_id"] not in selected or (reference_only and row["paragraph_id"] not in reference):
            exclusions["outside_selection"] += 1
            continue
        actor = row.get("actor_id")
        if actor is None:
            exclusions["unassigned_identity"] += 1
            continue
        if actor not in actor_ids:
            raise ValueError("Occurrence references unknown actor")
        unit = row.get(f"{scale}_id")
        if not unit:
            exclusions["missing_unit"] += 1
            continue
        units[unit].add(actor)
        unit_reports[unit] = row["report_id"]
    supports = defaultdict(list)
    for unit in sorted(units):
        for pair in itertools.combinations(sorted(units[unit]), 2):
            supports[pair].append(unit)
    degree, strength = Counter(), Counter()
    edges = []
    for (a, b), evidence in sorted(supports.items()):
        weight = len(evidence)
        edges.append({"source": a, "target": b, "weight": weight, "unit_ids": evidence})
        degree.update((a, b))
        strength[a] += weight
        strength[b] += weight
    nodes = []
    for index, row in enumerate(roster):
        aid = row["actor_id"]
        angle = 2 * math.pi * index / max(1, len(roster))
        nodes.append({"actor_id": aid, "name": row["name"], "degree": degree[aid], "strength": strength[aid],
                      "layout": row.get("layout", {"x": math.cos(angle), "y": math.sin(angle)})})
    return {"workflow": workflow, "scale": scale, "report_ids": sorted(selected), "reference_only": reference_only,
            "nodes": nodes, "edges": edges,
            "incidences": [{"unit_id": u, "report_id": unit_reports[u], "actor_ids": sorted(units[u])} for u in sorted(units)],
            "summary": {"nodes": len(nodes), "edges": len(edges), "isolates": sum(n["degree"] == 0 for n in nodes),
                        "total_weight": sum(e["weight"] for e in edges), "observed_units": len(units)},
            "exclusions": exclusions}


def import_verified_aliases(root, legacy_root):
    """Copy only saved alias strings after an exact roster/span bridge."""
    root, legacy_root = Path(root), Path(legacy_root)
    sources = [("canonical-analysis-ledger", root / "data/analysis_input.json"),
               ("legacy-annotation-records", legacy_root / "annotation_records.json"),
               ("legacy-actor-year-data", legacy_root / "actor_year_data.json")]
    snapshots = [(label, path, path.read_bytes()) for label, path in sources]
    ledger, records, old = (json.loads(payload) for _, _, payload in snapshots)
    native = {n["actor_id"]: n for n in ledger["nodes"] if n["workflow"] == "A"}
    identities = {r["actor_id"]: r for r in records["records"].values() if r.get("type") == "identity"}
    if set(native) != set(identities):
        raise ValueError("Legacy alias actor roster does not match canonical A roster")
    fields = ("actor_id", "report_id", "paragraph_id", "start", "end", "surface")
    current_spans = Counter(tuple(row.get(k) for k in fields) for row in ledger["occurrences"] if row["workflow"] == "A")
    legacy_spans = Counter(tuple(({"actor_id": row["actor_id"], **row["anchor"]}).get(k) for k in fields)
                           for row in old["occurrences"].values())
    if current_spans != legacy_spans:
        raise ValueError("Legacy occurrence bridge does not match canonical A spans")
    allowlist = []
    for actor_id, row in sorted(identities.items()):
        if row["canonical_name"] != native[actor_id]["name"]:
            raise ValueError("Legacy canonical name changed")
        aliases = _strings(row.get("aliases", []), "saved aliases")
        allowlist.append({"workflow": "A", "actor_id": actor_id, "name": row["canonical_name"], "aliases": aliases})
    result = {"schema": "pkoc-explorer-alias-allowlist-v1", "policy": "Saved display/search aliases only; never an automatic identity merge rule.",
              "actors": allowlist, "verification": {"actors": len(native), "bridged_occurrences": sum(current_spans.values()),
              "alias_strings": sum(len(r["aliases"]) for r in allowlist), "span_multiset_sha256": sha256(json_bytes(sorted(current_spans.items())))},
              "sources": [{"label": label, "artifact": path.name, "sha256": sha256(payload), "bytes": len(payload)} for label, path, payload in snapshots]}
    _public(result)
    for _, path, payload in snapshots:
        if path.read_bytes() != payload:
            raise ValueError("Alias input changed during snapshot")
    return result


def _unmil_display_layouts(ledger, layout_rows, key_rows):
    """Map every native L/A actor through the governed shared display dictionary.

    The paper's plot.R uses shared:<L actor> for verified one-to-one L/A
    correspondences, not workflow:<actor> for every native node. Missing,
    ambiguous or inconsistent mapping is an error; frozen L/A never falls back.
    R has no published layout and uses its own deterministic complete circle.
    """
    layouts = _unique(layout_rows, ["display_id"], "display layouts")
    points = {}
    for (display_id,), row in layouts.items():
        point = {key: float(row[key]) for key in ("x", "y")}
        if not all(math.isfinite(value) for value in point.values()):
            raise ValueError("Display layout has nonfinite coordinates")
        points[display_id] = point
    native = {(row["workflow"], row["actor_id"]): row for row in ledger["nodes"]
              if row["workflow"] in ("L", "A")}
    one_to_one = [row for row in ledger["correspondence"] if row.get("one_to_one") is True]
    l_to_a, a_to_l = {}, {}
    for row in one_to_one:
        left, right = row["L_actor"], row["A_actor"]
        if left in l_to_a or right in a_to_l or ("L", left) not in native or ("A", right) not in native:
            raise ValueError("Ambiguous or unavailable one-to-one display correspondence")
        l_to_a[left], a_to_l[right] = right, left
    expected = {}
    for workflow, actor in native:
        shared = actor if workflow == "L" and actor in l_to_a else a_to_l.get(actor) if workflow == "A" else None
        expected[workflow, actor] = "shared:" + shared if shared else workflow + ":" + actor
    keys = _unique(key_rows, ["display_id"], "display dictionary")
    mapped = {}
    for (display_id,), row in keys.items():
        for workflow in ("L", "A"):
            actor = row.get("actor" + workflow)
            if not actor:
                continue
            key = (workflow, actor)
            if key in mapped or key not in native or expected[key] != display_id:
                raise ValueError("Display dictionary has duplicate, unknown or mismatched native actor")
            if row.get("name" + workflow) != native[key]["name"]:
                raise ValueError("Display dictionary actor name changed")
            mapped[key] = display_id
    if set(mapped) != set(native) or set(points) != {key[0] for key in keys} or set(points) != set(expected.values()):
        raise ValueError("Display layout/dictionary does not cover the complete frozen L/A rosters")
    result = {key: dict(points[display_id]) for key, display_id in mapped.items()}
    reference = sorted(row["actor_id"] for row in ledger["nodes"] if row["workflow"] == "R")
    for index, actor in enumerate(reference):
        angle = 2 * math.pi * index / max(1, len(reference))
        result["R", actor] = {"x": math.cos(angle), "y": math.sin(angle)}
    return result


def build_unmil_bundle(root=ROOT):
    """Normalize frozen ledgers and prove all six native projections exactly."""
    root = Path(root)
    inputs = {}

    def read(relative):
        payload = (root / relative).read_bytes()
        inputs[relative] = payload
        return payload

    def read_json(relative):
        return json.loads(read(relative))

    def read_csv(relative):
        return list(csv.DictReader(io.StringIO(read(relative).decode("utf-8-sig"))))

    read("code/explorer_data.py")
    read("tools/export_explorer.py")
    read("config/study.json")
    read("code/plot.R")
    ledger = read_json("data/analysis_input.json")
    units = read_json("data/canonical_units.json")
    raw_claims = read_json("data/attribute_claims.json")["claims"]
    alias_data = read_json("data/explorer_aliases.json")
    if alias_data.get("schema") != "pkoc-explorer-alias-allowlist-v1":
        raise ValueError("Alias allowlist schema mismatch")
    alias_source = next(s for s in alias_data["sources"] if s["label"] == "canonical-analysis-ledger")
    if alias_source["sha256"] != sha256(inputs["data/analysis_input.json"]):
        raise ValueError("Alias allowlist does not match canonical ledger")
    aliases = {r["actor_id"]: r for r in alias_data["actors"]}
    source_rows = {r["report_id"]: r for r in read_csv("data/source_manifest.csv")}
    layouts = _unmil_display_layouts(ledger, read_csv("results/network_display_layout.csv"),
                                     read_csv("results/figure_stable_keys.csv"))
    definitions = read_json("protocol/codebook.json")["definitions"]
    reports = []
    for row in ledger["reports"]:
        source = source_rows[row["report_id"]]
        reports.append({**row, "document_symbol": source["document_symbol"], "official_url": source["official_url"]})
    nodes = []
    for row in ledger["nodes"]:
        saved = aliases.get(row["actor_id"]) if row["workflow"] == "A" else None
        if saved and saved["name"] != row["name"]:
            raise ValueError("Alias allowlist name mismatch")
        nodes.append({**row, "aliases": saved["aliases"] if saved else [],
                      "layout": layouts[row["workflow"], row["actor_id"]]})
    claims = []
    for row in raw_claims:
        literal, assignment = row.get("claim", {}), row.get("assignment", {})
        role = sorted(set(_array(assignment.get("role_codes"))))
        specialty = sorted(set(_array(assignment.get("specialty_codes"))))
        claim = {k: row.get(k) for k in ("workflow", "actor_id", "claim_key", "source_report_id", "observation_basis",
                                       "assumption", "support_status", "origin", "technical_status")}
        claim.update({"office_literal": literal.get("office_literal", literal.get("office_title", literal.get("role_literal"))),
                      "affiliation_literal": literal.get("affiliation_literal"), "capacity_status": literal.get("capacity_status"),
                      "role_codes": role, "specialty_codes": specialty, "cameo_codes": sorted(set(role + specialty)),
                      "assignment_status": assignment.get("status"), "report_years": _array(row.get("report_years")),
                      "evidence_ids": _array(row.get("evidence_ids")), "evidence_occurrence_ids": _array(row.get("evidence_occurrence_ids")),
                      "evidence_report_ids": _array(row.get("evidence_report_ids"))})
        claims.append(claim)
    claim_map = {(r["workflow"], r["actor_id"], r["claim_key"]): r for r in claims}
    attributes = []
    for row in ledger["dated_roles"]:
        selected = [claim_map[(row["workflow"], row["actor_id"], key)] for key in _array(row.get("applied_claim_keys"))
                    if (row["workflow"], row["actor_id"], key) in claim_map]
        attr = dict(row)
        attr["role_codes"] = sorted({code for claim in selected for code in claim["role_codes"]})
        attr["specialty_codes"] = sorted({code for claim in selected for code in claim["specialty_codes"]})
        for field in ("cameo_codes", "primary_cameo_codes", "applied_claim_keys", "primary_applied_claim_keys",
                      "source_evidence_issues", "uncertainty"):
            attr[field] = _array(attr.get(field))
        attributes.append(attr)
    interventions = []
    for row in read_csv("data/human_changes.csv"):
        interventions.append({"candidate_id": row["candidate_id"], "decision": row["decision"],
                              "human_added": row["human_added"].lower() == "true", "boundary_changed": row["boundary_changed"].lower() == "true",
                              "native_ids": json.loads(row["native_ids"]), "paragraph_id": row["paragraph_id"]})
    bundle = {"schema": SCHEMA,
              "dataset": {"id": "unmil-revision-04", "title": "UNMIL annotation and network study", "kind": "frozen-study",
                          "rosters": ["L", "A", "R"], "coordinate_policy": "paragraph-local zero-based half-open Unicode codepoints",
                          "year_policy": "Observations in reports; not continuous presence, tenure, or absence.",
                          "reference_policy": "Dependent same-researcher reference: 120 paragraphs, 6 reports; a bounded audit, not independent accuracy."},
              "reports": reports, "nodes": nodes, "occurrences": ledger["occurrences"], "claims": claims,
              "attributes": attributes, "paragraphs": units["paragraphs"], "sentences": units["sentences"],
              "interventions": interventions, "correspondence": ledger["correspondence"], "reference_units": ledger["reference_units"],
              "networks": [], "codebook": [{"code": code, "label": code, "definition": definition} for code, definition in sorted(definitions.items())],
              "provenance": {"inputs": [], "alias_bridge": alias_data["verification"], "limitations": [
                  "No source paragraphs, coding reasons, review journals, raw requests, or credentials are included.",
                  "Reconstruction is from archived extraction text; the historical PDF extractor is unknown.",
                  "CAMEO role and specialty fields are distinct; native union and explicit primary support remain unchanged.",
                  "Saved human decisions are fixed historical inputs; semantic support is not independently certified.",
                  "Unresolved source rights require private preparation; this export does not authorize publication."]}}
    validate_bundle(bundle)
    metrics = ("degree_normalized", "betweenness", "eigenvector", "eigenvector_weighted", "harmonic",
               "betweenness_inverse_weight", "local_clustering", "component", "core", "community")
    for workflow in ("L", "A"):
        for scale in SCALES:
            graph = project_network(bundle, workflow, scale)
            edge_rows = read_csv(f"results/network/{workflow}_{scale}_edges.csv")
            expected = {tuple(sorted((row["from"], row["to"]))): int(float(row["weight"])) for row in edge_rows}
            observed = {(row["source"], row["target"]): row["weight"] for row in graph["edges"]}
            if expected != observed:
                raise ValueError(f"Frozen edge/weight parity failed: {workflow}/{scale}")
            reference_nodes = {row["actor_id"]: row for row in read_csv(f"results/network/{workflow}_{scale}_nodes.csv")}
            if {row["actor_id"] for row in graph["nodes"]} != set(reference_nodes):
                raise ValueError("Frozen node/isolate parity failed")
            for node in graph["nodes"]:
                native = reference_nodes[node["actor_id"]]
                if any(node[k] != int(float(native[k])) for k in ("degree", "strength")):
                    raise ValueError("Frozen degree/strength parity failed")
                node["published_metrics"] = {key: float(native[key]) if native.get(key) not in (None, "", "NA", "NaN") else None for key in metrics}
            bundle["networks"].append(graph)
    bundle["provenance"]["inputs"] = [{"path": p, "sha256": sha256(v), "bytes": len(v)} for p, v in sorted(inputs.items())]
    validate_bundle(bundle)
    for relative, payload in inputs.items():
        if (root / relative).read_bytes() != payload:
            raise ValueError(f"Input changed during export: {relative}")
    return bundle


def graphml_bytes(graph):
    """Portable undirected GraphML; all native nodes, including isolates."""
    ns = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", ns)
    top = ET.Element(f"{{{ns}}}graphml")
    for key, scope, kind in (("name", "node", "string"), ("degree", "node", "int"), ("strength", "node", "int"),
                             ("weight", "edge", "int"), ("unit_ids", "edge", "string")):
        ET.SubElement(top, f"{{{ns}}}key", {"id": key, "for": scope, "attr.name": key, "attr.type": kind})
    g = ET.SubElement(top, f"{{{ns}}}graph", {"id": f'{graph["workflow"]}_{graph["scale"]}', "edgedefault": "undirected"})
    for row in graph["nodes"]:
        node = ET.SubElement(g, f"{{{ns}}}node", {"id": row["actor_id"]})
        for key in ("name", "degree", "strength"):
            ET.SubElement(node, f"{{{ns}}}data", {"key": key}).text = str(row[key])
    for index, row in enumerate(graph["edges"]):
        edge = ET.SubElement(g, f"{{{ns}}}edge", {"id": f"e{index}", "source": row["source"], "target": row["target"]})
        ET.SubElement(edge, f"{{{ns}}}data", {"key": "weight"}).text = str(row["weight"])
        ET.SubElement(edge, f"{{{ns}}}data", {"key": "unit_ids"}).text = json.dumps(row["unit_ids"], ensure_ascii=False)
    return ET.tostring(top, encoding="utf-8", xml_declaration=True) + b"\n"


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r"))):
        return "'" + value
    return value


def _csv_bytes(rows):
    stream = io.StringIO(newline="")
    fields = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _cell(v) for k, v in row.items()})
    return stream.getvalue().encode("utf-8")


def write_bundle(bundle, output, web_root=None):
    """Write deterministic source-free JSON/CSV/GraphML/ZIP to a new/empty directory.

    This function is shared by frozen-study export and new model-only case runs.
    It performs validation before creating any output. A supplied web_root is copied
    through a narrow static extension allowlist; tests and symlinks are excluded.
    """
    validate_bundle(bundle)
    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Output must be a new or empty directory")
    static = []
    if web_root is not None:
        web_root = Path(web_root)
        if not (web_root / "index.html").is_file():
            raise ValueError("Web source must contain index.html")
        for source in sorted(web_root.rglob("*")):
            relative = source.relative_to(web_root)
            if source.is_symlink():
                raise ValueError("Static web sources must not contain symlinks")
            if source.is_file() and source.suffix in {".html", ".css", ".js", ".mjs", ".svg"} and not any("test" in part.lower() for part in relative.parts):
                static.append((relative.as_posix(), source.read_bytes()))
    payload = json_bytes(bundle)
    files = {"bundle.json": payload,
             "bundle.js": ("window.PKOC_BUNDLE = " + payload.decode("utf-8").rstrip().replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029") + ";\n").encode("utf-8")}
    for name, key in (("reports", "reports"), ("actors", "nodes"), ("occurrences", "occurrences"), ("claims", "claims"),
                      ("attributes", "attributes"), ("interventions", "interventions"), ("paragraphs", "paragraphs"), ("sentences", "sentences")):
        files[f"downloads/{name}.csv"] = _csv_bytes(bundle[key])
    for graph in bundle["networks"]:
        stem = f'downloads/{graph["workflow"]}_{graph["scale"]}'
        files[stem + "_nodes.csv"] = _csv_bytes(graph["nodes"])
        files[stem + "_edges.csv"] = _csv_bytes(graph["edges"])
        files[stem + "_incidences.json"] = json_bytes(graph["incidences"])
        files[stem + ".graphml"] = graphml_bytes(graph)
    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            if name == "bundle.js":
                continue
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    files["downloads/annotations.zip"] = zip_stream.getvalue()
    for name, data in static:
        if name in files:
            raise ValueError("Static web source collides with generated data")
        files[name] = data
    manifest = {"schema": "pkoc-explorer-export-v1", "status": "validated_private_candidate",
                "dataset_id": bundle["dataset"]["id"], "bundle_sha256": sha256(payload),
                "source_text_included": False, "public_release_authorized": False,
                "files": [{"path": name, "sha256": sha256(data), "bytes": len(data)} for name, data in sorted(files.items())]}
    files["manifest.json"] = json_bytes(manifest)
    if web_root is not None:
        for name, data in static:
            if (web_root / name).read_bytes() != data:
                raise ValueError("Web input changed during packaging")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(files.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for row in manifest["files"]:
        if sha256((output / row["path"]).read_bytes()) != row["sha256"]:
            raise ValueError("Export changed during verification")
    return manifest
