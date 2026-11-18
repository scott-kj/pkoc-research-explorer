# Public explorer bundle contract

The PKOC UNMIL Network Explorer's normalized download uses pkoc-explorer-v1. JSON preserves exact values; CSV provides rectangular views with nested arrays/objects serialized as JSON cells. The [data dictionary](data-dictionary.md) explains each collection. The reusable toolkit continues to use this generic PKOC bundle format.

Required root keys are schema, dataset, reports, nodes, occurrences, claims, attributes, paragraphs, sentences, interventions, correspondence, reference_units, networks, codebook and provenance. Empty collections are arrays. Model-only imports declare rosters [L]; the frozen UNMIL example declares L, A and R.

Interactive study controls expose L and A. R and `reference_units` remain unchanged in the frozen bundle and annotation downloads for historical transparency; removing the Reference audit interface does not delete or reinterpret those records. R remains a dependent reference covering 120 selected paragraphs in six reports. It must not be treated as full-corpus ground truth or promoted to a normal construction branch. Older Reference audit view links resolve to Research workflow.

- Actor identity is (workflow, actor_id), not a name.
- Occurrence identity is (workflow, occurrence_id). Unresolved actor_id is null.
- Each occurrence references existing report/paragraph IDs and, when recorded, a containing sentence. Grounded spans use integer zero-based, half-open Unicode codepoints; unavailable positions remain null.
- Paragraph records contain identifiers and a SHA-256 declaration, never paragraph text. Sentence intervals refer to those canonical paragraphs.
- Claims keep office/affiliation literals, capacities, role/specialty codes, support status and evidence identifiers. Report-associated attributes retain the analytical union and primary-support union separately.
- Saved interventions expose only the original allowlisted fields. No session journal or narrative review reason is included.
- Networks contain native nodes, weighted edges, binary incidences, summary and exclusions. An edge includes the distinct supporting unit IDs. Isolates remain in the native roster.
- Public glossary prose is separate from scientific fields. Codes and all analytical records remain unchanged.

The browser validates relationships, declared branches, duplicate IDs, span consistency, paragraph hashes and all embedded projections before accepting an imported bundle. An internally consistent imported dataset is not automatically the trusted UNMIL study. Published advanced metrics are available only for the trusted embedded study and a supported complete construction. Local source text must match its declared paragraph hash before it is displayed.

## Graph presentation and image exports

Study coordinates, Circle, Random and 3D sphere layouts, dragged coordinates and camera state are presentation settings. Study coordinates is the display label for the existing `paper` setting; older URLs and downloaded settings retain that key. It uses saved study positions, with web-specific sizing, labels and framing rather than an identical manuscript figure. These settings do not change frozen `nodes[].layout`, annotation fields, the selected construction, incidence, edge weights or scientific snapshot. Apparent distance or depth does not encode an additional political relationship. Node size represents the number of neighbors in the constructed network, including when visibility controls hide some actors.

Hide isolates, CAMEO appearance, role visibility and label controls affect displayed marks only. The CAMEO appearance toggle controls role colors and the role legend; it does not remove role assignments or alter a selected role filter. Role and specialty fields remain available in data exports. Actor/edge inspection uses the same identifiers in normal and full-screen views.

SVG and PNG downloads capture the current graph presentation, including its viewport, layout, visibility and labels. They omit the surrounding application controls and inspector. They are image artifacts of a selected view, not complete analytical exports. CSV, incidences and GraphML continue to contain the complete constructed network, including actors hidden by display filters. Downloaded view settings describe the construction and presentation separately; neither image export nor rearrangement silently changes the frozen bundle or its expected hashes.

## Build and verify

```text
python tools/build_site.py --output site
python tools/verify_site.py site
node web/tests/check_bundle.cjs site/bundle.json
```

The destination must be new or empty. The builder checks the reviewed bundle SHA-256 and scientific snapshot before writing. It never updates expected hashes. The verifier checks every website byte, rejects extra files, compares the ZIP against displayed data and reconstructs all six native graphs. Publication requires the separate authorization record; passing a schema is not publication permission.

The generated site includes index.html, application assets, bundle.json, its escaped bundle.js wrapper, a complete manifest, attribution, and downloads. Downloads include annotations.zip, actors/occurrences/claims/attributes/interventions/reports/paragraphs/sentences CSVs and six sets of nodes, edges, incidences and GraphML. Correspondence, reference scope, glossary and provenance remain available in bundle.json and annotations.zip.

Within a recorded platform/runtime, repeated builds are byte-identical. ZIP creator/compression metadata may differ across platforms. Original upstream audits also observed tiny generated R-layout roundoff; it did not change annotations or network weights. This public snapshot freezes the reviewed Windows bundle's scientific and layout values. Each built artifact has its own manifest.

## Publication boundary

The site contains no complete source paragraphs, archived report text, manuscript, model weights, private paths, credentials or raw inference logs. See [NOTICES](../NOTICES.md) and [publication review](publication-review.md). For exact structured values use JSON; formula-like string values in CSV receive a leading apostrophe to prevent spreadsheet execution.
