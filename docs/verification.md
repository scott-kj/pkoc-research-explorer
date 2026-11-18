# Verification scope

## 18 November 2026 redesign and content alignment

The content audit, local test suites and browser review passed. Commit-specific Windows/Linux checks and deployment are recorded by the [publication workflow](https://github.com/scott-kj/pkoc-research-explorer/actions/workflows/pages.yml). Earlier verification records below retain their original scope and results.

The content audit used manuscript Revision 4.2, dated 18 November 2026, alongside the released UNMIL bundle. Revision 4.2 is a writing revision of scientific release `20261109_review_v1`, not a new annotation or analytical dataset. An in-memory comparison with the maintained scientific export found exact equality for all 14 preserved scientific root collections listed in `publication.json`. The approved public bundle remains byte-identical. No manuscript, source archive, private review material or new inference output is added by this alignment.

| Clarification | Public evidence or manuscript reference | Effect on the explorer |
| --- | --- | --- |
| The corpus and native networks are unchanged. | `reports`, `paragraphs`, `sentences`, `nodes`, `occurrences`, `networks`; Revision 4.2 Sections 3.1, 3.4 and 4.2. | Retain 41 reports, 3,075 paragraphs, 12,198 sentence intervals; L/A rosters 125/117 and the six exact projections. |
| L and A are dependent workflows. | `dataset.reference_policy`, `correspondence`, `interventions`; Revision 4.2 Sections 3.2 and 5.4. | Explain L as the executed model workflow and A as its human-reviewed continuation; do not infer a causal benefit of review. |
| R is a bounded, exposed same-researcher reference with two documented omissions. | `reference_units`, R rows in `occurrences` and `nodes`; public research-workflow disclosure; Revision 4.2 Sections 3.3 and 4.1. | State 120 paragraphs, six reports, 25 mentions and 15 people. Preserve the recorded labels and denominator. |
| A's 238 linked targets cover 96 actors, separately from 117 completed profiles. | `attributes.workflow`, `primary_cameo_codes`, `actor_id`; Revision 4.2 Section 4.5. | Label 280 native targets, 238 linked targets and 96 covered actors separately. Do not assign 96 actors to all 280 targets. |
| Recorded source support does not establish semantic accuracy or measured savings. | `claims`, `attributes`, `interventions`, `provenance.limitations`; Revision 4.2 Sections 4.5 and 5.4. | Disclose the lack of systematic office/affiliation validation and a measured manual labor/cost comparison. |
| Study coordinates preserves positions, not an identical paper drawing. | `nodes.layout`, graph presentation settings; Revision 4.2 companion supplement Section S4. | Clarify the label while preserving the historical `paper` key and separate web degree sizing. |

Three record-interpretation corrections are independently inspectable in the released data. Saved candidate decisions now link only through exact `candidate_id`/`native_ids` and occurrence IDs in the same paragraph and selected branch; shared decisions are deduplicated, and unmatched records remain in corpus downloads. Coding coverage counts nonempty analytical codes and nonempty explicit primary support separately over observed actor-report targets, with empty and orphan attribute records handled explicitly. Interactive GraphML now carries the same supporting `unit_ids` evidence as prebuilt exports, alongside unchanged weights and node attributes. These changes do not edit annotations or imply complete actor adjudication histories.

Local Windows validation used CPython 3.12.14 and Node 24.18.0: **50 JavaScript tests**, **39 portable-pipeline tests**, **four onboarding tests**, and **seven publication tests** passed. New regression cases cover exact branch-scoped decision matching, shared/rejected/unresolved decisions, empty coding records, observed-report denominators and GraphML evidence IDs. The scripted fictional example completed with 16 controlled-fixture requests and no external calls. The publication verifier checked all 50 artifact files and the approved bundle hash; the independent projector reproduced all six networks exactly, including isolates and unit evidence: L has 125 nodes and 116/186/929 edges; A has 117 nodes and 128/196/887 edges at sentence/paragraph/report scales. Documentation links and JavaScript syntax also passed checks.

Browser review covered dark/light persistence, all four layouts, sphere background rotation and surface dragging, keyboard actor and edge inspection, reset controls, full-screen Escape and focus return, deep links, actor search and report-count tables, contact links, imported inventories and generic toolkit routes. A fictional imported bundle with Unicode and HTML-looking actor names rendered as literal text; five matching local source paragraphs loaded without uploading. No application console errors were observed. At 375, 768, 1024 and 1440 pixels there was no horizontal page overflow; the inspector changed to the adjacent desktop position at 1024 pixels and mobile popovers stayed inside the viewport. Keyboard focus was visible. Audited normal/secondary/action text contrasts all exceeded 4.5:1 in both themes (lowest tested secondary-text pair: 5.46:1). Reduced-motion CSS disables transitions, animation and smooth scrolling.

Actual SVG/PNG downloads were visually reviewed. The matching sphere fixture exported a 1080 × 879 SVG and a 2160 × 1758 PNG, with Unicode labels, CAMEO/degree legends and the selected −90° orientation. The SVG contained no script, external image or foreign-object elements. The downloaded GraphML preserved three nodes, its isolate, one edge of weight two and both contributing paragraph IDs. Imported workflow links opened the loaded report inventory or generic toolkit guidance, without presenting UNMIL history as evidence for the imported run. No new LLM inference or 1,000-draw study was required or performed for this presentation update.

## Optional light theme

The original dark appearance remains the first-visit default. A locally saved light/dark preference applies before styles load and is available in the header and full-screen graph toolbar. Theme changes update presentation only, without rebuilding the network or resetting positions, orientation, filters or selections. Image captions, legends and graph colors follow the active theme; safe computed shadow outlines are retained for pale CAMEO isolates.

Local Windows validation passed all **43 JavaScript tests** and **seven publication tests**. New export cases check the unchanged default dark footer, the light palette and rejection of unsafe palette values. The publication verifier checked all **50 artifact files**, the unchanged approved annotations, and exact parity of all six UNMIL networks. The existing Windows/Linux toolkit checks remain deployment gates; this change does not run new inference or repeat the historical full study.

Browser checks confirmed dark on first visit, light and dark persistence after reload, synchronized keyboard controls, full-screen theme switching, unchanged graph DOM and selection across a switch, readable workflow/table views, and no horizontal page overflow at 375 and 1440 pixels. Light SVG/PNG downloads used the light background, readable labels/caption and degree key; the corrected SVG also retained the pale-isolate outline and CAMEO legend. The browser reported no application errors. The [Actions workflow](https://github.com/scott-kj/pkoc-research-explorer/actions/workflows/pages.yml) records commit-specific platform checks and deployment.

## November 12, 2026 explorer revision

This revision adds Paper, Circle, deterministic Random and rotatable 3D sphere arrangements; degree-based node area; a combined CAMEO appearance toggle; visible isolate controls; an adjacent evidence inspector; current-view SVG/PNG export; a linked research framework; and the author's contact page. The interactive R view is retired, while the frozen R records and historical disclosure remain available. L is described as the executed model workflow and A as its human-reviewed continuation, consistently with the historical methods.

Local Windows checks used CPython 3.12.14 and Node 24.18.0. All **40 JavaScript tests**, **39 portable pipeline tests**, **four onboarding tests**, and **seven publication tests** passed. The controlled-server Python fixtures required loopback access outside the local execution sandbox; they made no paid or external inference calls. CI retains its existing Node 22 and exact Python 3.12.14 declarations.

The publication verifier checked 48 artifact files and the unchanged approved annotation snapshot. The independent JavaScript projector matched all six networks, including incidence evidence, isolates and exact weights: L sentence/paragraph/report have 116/186/929 edges and 125 nodes; A has 128/196/887 edges and 117 nodes. Original study replays and manuscript checks below retain their historical scope; this interface revision does not rerun LLM inference or the 1,000-draw study.

New geometry tests cover deterministic arrangements, unchanged paper coordinates, separate layout/context state, reversible 3D rotation, hemisphere-preserving surface movement, frontmost picking, stable keyboard order, degree-area scaling, click-to-place cancellation and source-object immutability. Export tests cover XML/Unicode text, dimensions, filenames and wrapping of legends and captions.

Real browser checks covered layout switching and position retention after filtering, neutral/CAMEO appearance, background orbit, single-node dragging, arrow-key movement, click-to-place, Escape cancellation, full-screen exit, keyboard edge evidence, old R links, contact information, local model-only bundles and malicious-looking actor names rendered as text. A malformed grounding fixture was rejected without replacing the loaded study. Layouts at 375, 768, 1024 and 1440 pixels had no horizontal page overflow; the inspector moved alongside the graph at 1024 pixels and the framework stacked vertically on mobile. No application console errors were observed.

Actual SVG and PNG downloads were inspected. The PNG dimensions were exactly twice those of its SVG counterpart, Unicode labels remained readable, and the neutral-color export omitted the CAMEO key. A full-screen SVG retained the composed camera, enabled role key, degree key, selection/filter caption and sphere orientation. The export contained no script, external image or foreign-object elements. Optional source prose and the inspector are excluded from image serialization.

Commands used:

```text
node --test web/tests/*.test.cjs
python -m unittest discover -s code -p "test_case_pipeline*.py"
python -m unittest discover -s tools -p "test_*.py"
python tools/run_demo.py --output runs/browser-demo
python tools/build_site.py --output <new-build-directory>
python tools/verify_site.py <new-build-directory> --require-public-approval
node web/tests/check_bundle.cjs <new-build-directory>/bundle.json
```

The fictional example again completed 16 scripted fixture requests, five paragraphs and three actors. The [Actions workflow](https://github.com/scott-kj/pkoc-research-explorer/actions/workflows/pages.yml) records commit-specific Windows/Linux checks and deployment. Local paths, browser fixtures, screenshots and generated builds are excluded from the source commit.

## Earlier interactive graph update

The enlarged graph adds a separate presentation module for dragging, panning, zooming, label selection and full-screen exploration. It keeps copied coordinates apart from the immutable annotation bundle. Four new JavaScript checks cover fit bounds, pointer-centered zoom, zoomed movement and layout-copy integrity; all 24 JavaScript tests and seven publication checks pass locally. The six UNMIL projections retain exact parity.

Browser checks exercised node dragging after zoom, arrow-key and button movement, position retention across role filters, reset, all-label selection, full-screen evidence dialogs, exit, navigation cleanup, and a 375-pixel layout without horizontal overflow. The application reported no console errors. These checks concern interface behavior, not inference accuracy. The Actions history records the published commit's Windows/Linux toolkit checks and deployment.

The public site is a distribution of the verified UNMIL explorer. Its upstream source is commit 520c4fd8617bbae7775f1704503de0aab184f9ee, whose execution inputs match the previously tested commit 0f63c4b1c6b18c341af98b181422460ff6fc0968.

Upstream Windows and Linux checks passed 213 Python tests, 17 JavaScript tests, five-draw smoke analysis, restored pinned environments and full 1,000-draw replays. All 70 reference comparisons passed on each OS; maximum applicable floating differences were 1e-14 and 2.8e-14 against the 1e-9 tolerance. Structural data remained exact. These are historical upstream checks, not new runs performed by this website repository.

Local archived-text reconstruction matched 41 texts, 3,075 paragraphs and 12,198 sentence boundaries. No source archive was uploaded to hosted CI. The regenerated article and supplement matched all 41 sealed pages. Neither this transfer nor original AI-assisted checks are independent human review.

The bounded local inference engineering tests used 35 of 100 authorized attempts with zero paid API calls. The original run retained one office-extraction failure after two attempts; a separate one-request authentication probe intentionally stopped partial. UNAMSIL was an engineering example, not a second study or new comparative finding.

For this publication, the reviewed scientific snapshot preserves dataset identity, all actor/occurrence/claim/attribute records, saved interventions, unit IDs/hashes/boundaries, correspondence, reference scope and all network products exactly. Only public glossary prose and publication provenance differ from the private bundle. The recorded scientific hash covers every preserved root collection. No source archive is released and no scientific reference output was replaced.

The original site ran 17 independent JavaScript domain tests and exact six-network parity check, plus publication-specific tests for snapshot protection, output isolation, ZIP fidelity and unexpected-file rejection. Current commands and deployment results are visible in this repository's Actions tab. Network parity includes binary incidences, native isolates, edge weights, supporting units, degree and strength.

Prior real browser tests covered actor/year filtering, actor and edge drill-down, downloads, deep links, keyboard operation, mobile layout, safe rendering, local bundle/source loading and Unicode highlighting. Publication-specific browser checks additionally exercise the public navigation and downloads. Historical tests retain their own scope; a passing projection does not validate model predictions or source rights.

## Public toolkit and interface update

The November 2026 update maintains the frozen scientific bundle and all six projections. Its new validation scope is the portable toolkit, onboarding example and redesigned interface; it does not repeat or extend the historical 1,000-draw manuscript study.

Local Windows validation used Python 3.12.14 and passed 39 portable pipeline tests, four public-onboarding tests, seven publication tests, and 20 JavaScript domain tests. The added JavaScript cases cover report-scoped CAMEO roles, multiple-role presentation, and role/specialty GraphML export. The independent projector and publication verifier checked all six UNMIL networks, preserving rosters, isolates, incidence, supporting units and exact weights (L/A: sentence 116/128, paragraph 186/196, report 929/887).

The documented fictional demonstration completed with 16 scripted inference requests, five paragraphs and three actors. Its paragraph graph has one edge of weight two and one isolate; its report graph has three edges. There were zero external inference calls. Tests also check default preflight without provider contact, output protection, synthetic metadata and versioned local-library verification. This is a runnable engineering fixture, not a model accuracy test.

Real browser checks covered the network landing page, role filtering, unchanged construction counts under visibility filters, keyboard tabs and actor selection, reset, actor/year search, actor details, edge evidence, deep links restored after reload, GraphML download, local fictional-bundle loading, and layouts at 375, 768 and 1440 pixels. No horizontal page overflow or browser console errors were observed. The downloaded GraphML retained GOV/IGO/MED roles, an isolate and the expected weight. Raw integrity values are absent from the visible interface; reproducibility metadata remains in downloads and optional record details.

The GitHub workflow tests this public toolkit on both Windows and Linux using controlled fixtures, runs the same fictional example, verifies that tracked files remain unchanged, and gates Pages deployment on those jobs plus publication checks. Consult the [Actions history](https://github.com/scott-kj/pkoc-research-explorer/actions/workflows/pages.yml) for current commit-specific platform and deployment results. No paid external inference or fresh real-model execution is part of this update.

### Exact Windows CI runtime

Windows uses the previously validated Astral managed CPython bootstrap because the setup-python catalog lacks Python 3.12.14 for that runner. The workflow pins setup-uv v9.0.0 by commit, uv 0.13.7 by version and archive checksum, creates an isolated environment, and asserts CPython 3.12.14 and 64-bit architecture before tests. Linux continues to use setup-python with the same Python version. This does not add a toolkit runtime dependency or permit fallback to a different interpreter. See [Astral's managed Python documentation](https://docs.astral.sh/uv/guides/install-python/) and the exact pins in [the workflow](../.github/workflows/pages.yml).
