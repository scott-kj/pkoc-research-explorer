# Public explorer bundle contract

The normalized download uses pkoc-explorer-v1. JSON preserves exact values; CSV provides rectangular views with nested arrays/objects serialized as JSON cells. The [data dictionary](data-dictionary.md) explains each collection.

Required root keys are schema, dataset, reports, nodes, occurrences, claims, attributes, paragraphs, sentences, interventions, correspondence, reference_units, networks, codebook and provenance. Empty collections are arrays. Model-only imports declare rosters [L]; the frozen UNMIL example declares L, A and R.

- Actor identity is (workflow, actor_id), not a name.
- Occurrence identity is (workflow, occurrence_id). Unresolved actor_id is null.
- Each occurrence references existing report/paragraph IDs and, when recorded, a containing sentence. Grounded spans use integer zero-based, half-open Unicode codepoints; unavailable positions remain null.
- Paragraph records contain identifiers and a SHA-256 declaration, never paragraph text. Sentence intervals refer to those canonical paragraphs.
- Claims keep office/affiliation literals, capacities, role/specialty codes, support status and evidence identifiers. Report-associated attributes retain the analytical union and primary-support union separately.
- Saved interventions expose only the original allowlisted fields. No session journal or narrative review reason is included.
- Networks contain native nodes, weighted edges, binary incidences, summary and exclusions. An edge includes the distinct supporting unit IDs. Isolates remain in the native roster.
- Public glossary prose is separate from scientific fields. Codes and all analytical records remain unchanged.

The browser validates relationships, declared branches, duplicate IDs, span consistency, paragraph hashes and all embedded projections before accepting an imported bundle. An internally consistent imported dataset is not automatically the trusted UNMIL study. Published advanced metrics are available only for the trusted embedded study and a supported complete construction. Local source text must match its declared paragraph hash before it is displayed.

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
