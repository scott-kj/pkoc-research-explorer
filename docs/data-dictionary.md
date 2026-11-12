# PKOC UNMIL Network Explorer annotation data dictionary

The authoritative normalized download is `bundle.json` with schema `pkoc-explorer-v1`. CSV files are convenient rectangular views of the same rows; they do not replace the JSON types. See the [contract and export commands](explorer-data-contract.md) and [research workflow](research-workflow.md).

IDs are stable within the frozen release or a particular hash-bound case run. An actor is identified by **`(workflow, actor_id)`**, never by name alone. An occurrence is identified by **`(workflow, occurrence_id)`**. Names can be shared by different people; aliases are search aids rather than automatic equivalence rules. New case IDs need not equal UNMIL IDs.

## Common conventions

| Convention | Meaning |
|---|---|
| `L` / `A` / `R` | Frozen executed model workflow / human-reviewed continuation / bounded dependent-reference branch. Historical L includes recorded deterministic processing and capacity amendments; it is not a controlled model-alone evaluation. A new automated case contains model-only L output. |
| `null` | Not recorded, unresolved or not applicable, according to the field and its status. It is not numeric zero, proof of absence, or an invented date. |
| `[]` | No recorded members of that collection. Inspect status/coverage to distinguish valid empty output from failure or unavailable support. |
| `start`, `end` | Zero-based, half-open Unicode codepoint offsets in the canonical paragraph. Python `text[start:end]` is the intended slice. |
| Dates | ISO date with available precision; no missing month/day is invented. UNMIL's recorded publication dates are full dates. |
| Year counts | Observations in reports published in that year, not continuous presence or tenure. A blank does not establish absence. |
| SHA-256 | Lowercase hexadecimal digest of exact bytes; paragraph text hashes cover UTF-8 text without an added newline. |
| CSV nested values | Arrays and objects are JSON-encoded inside a quoted CSV cell. Parse the cell with JSON rather than splitting on commas. |
| CSV missing/boolean values | `null` becomes an empty cell; booleans become `true`/`false`. Use JSON to distinguish absent, null and empty string exactly. |
| Spreadsheet protection | Literal string cells beginning with formula triggers are prefixed with `'`. JSON retains the original string. |

## Dataset and reports

`dataset` identifies the bundle (`id`, `title`), `kind` (`frozen-study` or `model-only`), available `rosters`, coordinate policy and interpretation limits. Frozen UNMIL includes a report-year observation policy and the explicit R scope. `provenance` records input/code hash entries and limitations. New cases may add coverage/status summaries and flags such as `human_reviewed:false`; they must not include native request logs, credentials or local paths.

| Report field | Definition |
|---|---|
| `report_id` | Stable source/document identifier referenced by every paragraph and occurrence. |
| `document_symbol` | Official UN symbol, such as `S/2000/13`. The symbol is checked against actual files; a catalog filename is not sufficient authority. |
| `official_url` | HTTPS provenance link to the official document. It is not a claim that a fresh PDF matches archived extraction bytes. |
| `report_date`, `year` | Recorded publication date and its year, or null when not known. |
| `paragraphs`, `words` | Frozen corpus coverage counts where available. |
| `era` | Historical analysis stratum; not a new temporal finding. |

Reports appear in `reports` and `downloads/reports.csv`. The original [source manifest](../data/source_manifest.csv) remains the authority for inclusion/exclusion, extraction-file hashes and document reuse status.

## Actor roster

Actors appear in `nodes` and `downloads/actors.csv`.

| Actor field | Definition |
|---|---|
| `workflow`, `actor_id`, `name` | Native branch, stable identity and display name. |
| `aliases` | Explicitly transferred saved aliases (A), or an empty list when no alias handoff exists. They are not inferred from display-name similarity. |
| `cameo_codes`, `cameo_label` | Native analytical actor-level code union and display label. |
| `primary_cameo_codes`, `primary_cameo_label` | Native codes restricted to explicitly supported source evidence under the study's primary support rule. |
| `role_descriptive`, `role_model`, `role_coverage` | Historical broad-role descriptor, machine role and coverage status. These are distinct from literal offices and CAMEO role codes. |
| `attribute_provenance` | Whether the frozen actor attributes originate in machine/native or saved human records. |
| `observed_report_dates`, `supported_report_dates` | Recorded date coverage for the actor's attributes. |
| `coded_reports`, `eligible_reports`, `primary_coded_reports` | Report-level coding coverage counts. |
| `cameo_partial_coding`, `primary_cameo_partial_coding` | Explicit partial-coding flags; missing coverage must not be converted to a substantive category. |
| `applicability_assumption_reports` | Number of associated reports using documented applicability assumptions. |
| `layout` | Finite SVG coordinates `{x,y}` for stable presentation; not a scientific variable. Frozen L/A actors use the complete governed shared display mapping; a missing or inconsistent mapping fails export. Archived R records use a separate deterministic circle and remain in downloads. Interactive layout choices do not overwrite these frozen coordinates. |
| `identity_origin` | Optional case-pipeline marker such as `model-only`. It does not imply human verification. |

The frozen A alias allowlist records source artifact basenames/hashes and the exact 578-observation bridge for 117 actors. It contains 174 strings. It omits the old HTML, raw journals, embedded paragraphs and unrelated annotation records.

## Occurrences and units

Occurrences appear in `occurrences` and `downloads/occurrences.csv`.

| Occurrence field | Definition |
|---|---|
| `workflow`, `occurrence_id` | Branch-scoped unique mention/prediction identifier. |
| `actor_id` | Assigned native identity, or null for an unresolved identity. Null identity is excluded from network incidence. |
| `report_id`, `report_date` | Source report and recorded publication date when available. |
| `paragraph_id`, `sentence_id` | Canonical containing units. A sentence ID may be null when no exact position is known. |
| `start`, `end`, `surface` | Exact source span coordinates and mention literal where grounded. Coordinates are both null when ungrounded; do not infer them from displayed name. |
| `grounding_status` | `grounded` for a mechanically exact canonical span; historical `raw_prediction_no_exact_span` retains unavailable positions. New cases also preserve explicit non-grounded outcomes. Exact matching does not validate the person's identity or claim semantics. |
| `identity_status` | Optional explicit new-case identity resolution status/uncertainty. |

`paragraphs` / `downloads/paragraphs.csv` contain `paragraph_id`, `report_id`, optional `publication_date`, and `text_sha256`. They contain **no paragraph text**. `sentences` / `downloads/sentences.csv` contain `sentence_id`, `paragraph_id`, `report_id`, `start` and `end`. Bounds refer to the original canonical paragraph. There are 3,075 paragraphs and 12,198 sentence intervals in frozen UNMIL.

For optional local evidence inspection, load reconstruction `paragraphs.jsonl` rows containing `paragraph_id` and `text`; each text must match the bundle's SHA-256 before highlighting. The browser must convert codepoint offsets instead of applying JavaScript UTF-16 `slice` directly. Source text is not uploaded or packaged by the explorer export.

## Claims and report-associated attributes

Claims appear in `claims` and `downloads/claims.csv`. A claim key is scoped to `(workflow, actor_id)`.

| Claim field | Definition |
|---|---|
| `claim_key` | Stable claim identifier linking report attributes to the underlying assignment. |
| `office_literal`, `affiliation_literal` | Recorded literal office/affiliation string, or null; not a verified biography or source paragraph. |
| `capacity_status` | Recorded capacity such as current/former/unknown where available. It is not a computed tenure interval. |
| `role_codes` | CAMEO role/sector assignment from the claim. |
| `specialty_codes` | Separately recorded CAMEO specialty assignment. |
| `cameo_codes` | Union of that claim's role and specialty codes. The corresponding native report/actor union is preserved separately. |
| `assignment_status`, `technical_status` | Assignment/transport/schema status where recorded; passing mechanical checks is not independent semantic certification. |
| `evidence_ids`, `evidence_occurrence_ids`, `evidence_report_ids` | Available explicit support identifiers. An empty list must not be replaced with guessed evidence. |
| `source_report_id`, `report_years` | Source report and report-year observation coverage. |
| `observation_basis`, `assumption` | Basis for applicability and whether an assumption is recorded. Report-year assumptions do not prove explicit support in every report. |
| `support_status`, `origin` | Recorded support qualification and machine/human origin. |
| `role_literal` | Optional literal role field in automated case output. |

Narrative model reasons, review notes, private recovery metadata, proposal bundles and complete source paragraphs are deliberately excluded. Office/name literals remain source-derived material subject to the [rights notice](../NOTICES.md).

Attributes appear in `attributes` and `downloads/attributes.csv`, uniquely keyed by `(workflow, actor_id, report_id)`.

| Attribute field | Definition |
|---|---|
| `role_codes`, `specialty_codes` | Separately derived sets from applicable normalized claim assignments. |
| `cameo_codes` | **Unchanged native analytical union** in the frozen report-associated ledger. It is not replaced with the older matrix's color convention. |
| `primary_cameo_codes`, `primary_cameo_label` | Unchanged explicit-source-support code set and label. |
| `applied_claim_keys`, `primary_applied_claim_keys` | Claims used in the broader applicability view and the stricter primary-support view. |
| `applicability_assumption`, `source_evidence_issues`, `uncertainty` | Recorded limitations rather than hidden corrections. |
| `role`, `role_set`, `primary_role_set`, `office_claim_count` | Historical broad-role summary, full/primary role sets and claim count. |
| `provenance`, `report_date` | Recorded branch provenance and report observation date. |

The 28-code public glossary is exposed as `{code,label,definition}`. It provides newly written short explanations of CAMEO actor identifiers; it does not distribute the manual. Analytical codes and assignments are unchanged.

## Human intervention and branch correspondence

`interventions` / `downloads/interventions.csv` contain the available safe fields from `human_changes.csv`: `candidate_id`, `decision`, `human_added`, `boundary_changed`, `native_ids`, and `paragraph_id`. They show which saved candidate decisions are available; they do not constitute a complete session journal or a claim about annotation time. They are empty for new automated cases.

`correspondence` contains the frozen L/A span-based mapping: `L_actor`, `L_name`, `A_actor`, `A_name`, `shared_spans`, `one_to_one`. This is an analytical mapping, not a license to merge native rosters. A continues from compatible L proposals; the correspondence does not make the branches independent. `reference_units` lists the 120 paragraph IDs defining the historical R comparison scope across six reports. The records remain in downloads; the website does not offer an interactive R branch.

## Network products

Each `networks` entry has `workflow`, `scale`, selected `report_ids`, `reference_only`, `nodes`, `edges`, `incidences`, `summary`, and `exclusions`.

| Product | Fields and interpretation |
|---|---|
| Nodes | `actor_id`, `name`, `degree`, `strength`, `layout`; all native actors, including isolates. `published_metrics` is optional and valid only for the unchanged supported baseline network. |
| Edges | `source`, `target`, positive integer `weight`, distinct `unit_ids`. The edge is undirected; weight counts shared textual units. |
| Incidences | `unit_id`, `report_id`, `actor_ids`. Each actor appears at most once per unit; singleton units are retained. Units with no actor have no incidence row. |
| Summary | `nodes`, `edges`, `isolates`, `total_weight`, `observed_units`. |
| Exclusions | `unassigned_identity`, `missing_unit`, `outside_selection` counts, with the same branch/selection scope as the projection. |

`published_metrics` may include degree normalization, betweenness, eigenvector variants, harmonic centrality, clustering, component, core and community. They are carried from reviewed baseline outputs, not recomputed for arbitrary views. Basic degree/strength and edge weights are transparently recomputed from the selected incidences.

Download files are `{workflow}_{scale}_nodes.csv`, `_edges.csv`, `_incidences.json`, and `.graphml`. GraphML includes isolates and edge support IDs. The default frozen export supplies the six L/A networks. R annotations and reference-unit identifiers remain in `bundle.json` and the complete annotation download for historical inspection, without an interactive R projection. Any reconstruction from those records must restrict incidence to the selected paragraphs, including at report scale.

## Citation, licensing and publication

Cite [CITATION.cff](../CITATION.cff), the exact repository version, the unpublished manuscript, and `manifest.json`/`bundle.json` hashes. Explain any filter or new inference settings. Original code is MIT; original annotation/documentation contributions are CC BY 4.0; source text, source-derived material, CAMEO, models and other third-party material are excluded from those grants. The separate publication.json record governs this structured-data distribution. The source archive remains private while the documented reuse questions remain unresolved.

## Explorer role controls and current-view exports

The network role legend and filter aggregate `attributes.role_codes` only over the selected reports in the selected workflow. Multiple roles retain a separate display category; an empty role set means not recorded in that scope. Specialties and the analytical union remain separate. These are display controls, not additional network exclusions. The CAMEO appearance toggle changes colors and the legend, preserving any selected role filter. Current-view node CSV and GraphML downloads carry `role_codes` and `specialty_codes` from that report selection. Saved view settings include `display.cameo_role` and `role_scope: selected_reports`. Construction, isolates, edge weights and the frozen bundle are unchanged.

Paper, Circle, Random and 3D sphere are alternative graph presentations. Node size reflects degree in the complete constructed network; hide-isolate and other visibility controls do not recalculate degree. Downloaded view settings keep presentation separate from construction. SVG and PNG images capture the current visible graph, while node/edge tables, incidences and GraphML retain the full constructed network, including hidden actors. See the [presentation contract](explorer-data-contract.md#graph-presentation-and-image-exports).
