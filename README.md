# PKOC UNMIL Network Explorer

Explore the documented UNMIL research example by Krerkkaiwan Kajohnkunchonlathorn, inspect the evidence behind its networks, and download its structured annotations. The repository also includes a reusable PKOC annotation-to-network toolkit for researcher-selected English reports.

**[Open the explorer](https://scott-kj.github.io/pkoc-research-explorer/)**

**[Toolkit setup and runnable example](docs/quickstart.md)** · **[Full toolkit guide](docs/toolkit.md)** · **[Research workflow](docs/research-workflow.md)**

The research explanation is aligned with manuscript Revision 4.2, dated 18 November 2026. The released UNMIL annotations and six native networks remain the same frozen scientific snapshot. The manuscript remains unpublished and is not distributed here.

## Explore and download

The original dark theme remains the default. Choose **Light mode** in the header or graph toolbar for a light background; **Dark mode** restores the original appearance. Your preference is saved in this browser, including after reload. Theme changes preserve your filters, selections and graph positions. SVG and PNG downloads use the selected theme.

The website opens directly to the network explorer. CAMEO role colors, named filters, and a labeled legend reflect the selected reports. Toggle the CAMEO display to use neutral nodes and hide the role legend without changing the annotations or role selection. Multiple roles stay multiple; specialties remain separate. **Hide isolates** hides actors with no neighbors in the constructed network. Display controls change visibility, while table and GraphML exports retain the complete constructed network. Raw provenance and integrity values stay in downloadable files rather than the main interface.

- Follow the linked [research framework and workflow](docs/research-workflow.md) from report checks and cleaning to annotation, human review, and network comparison.
- Search actor × year observations, inspect actor records and examine the distinct units supporting each edge.
- Switch L/A and sentence/paragraph/report contexts. Reset to the complete UNMIL paper preset. The limited historical R reference remains documented and included in the frozen downloads; it is not an interactive branch on the website.
- Download annotations, actor and edge tables, incidence lists, GraphML and view settings, or save the current graph as SVG or PNG.
- Load compatible JSON bundles or verified source text locally. The application does not upload these files or request API credentials.

The larger graph supports mouse/touch dragging, background panning, zoom controls, and **Full screen**. Choose **Study coordinates**, **Circle**, **Random**, or **3D sphere** to rearrange the same network. Study coordinates uses the saved study positions; web sizing, labels and framing differ from the manuscript figures. Position and apparent depth do not encode measured relationships. Node size represents **degree**, the number of connected actors; mention counts and total edge weight are separate measures.

Smart labels avoid overlaps; choose **All labels** to see every name or **Selected only** to focus on one actor. Names stay readable while zooming. Focus a node and use arrow keys to move it (Shift moves farther). **Fit** frames the current positions. Actor and edge details appear beside the graph on wide screens and below it on smaller screens, including in full-screen mode.

Dragged positions persist across filters within the current page session and are included in downloaded view settings. They do not change annotations, edges, weights, or scientific exports, and they are not restored from a URL after reload. SVG and PNG images capture the current graph view, including its display filters, layout, labels, and camera; they are illustrations of that view, not substitutes for the complete network tables. Full-screen mode retains the evidence panel and dialogs; Escape or **Exit full screen** returns to the page. Browsers that restrict the Fullscreen API use a full-window workspace.

Year cells count observations in published reports; blanks do not establish absence or tenure. Edges represent undirected co-occurrence, not interactions or alliances. The [data dictionary](docs/data-dictionary.md) explains identity, uncertainty, human decisions and source support.

L is the executed model workflow; A is its human-reviewed continuation. Their dependence prevents a causal estimate of the benefit of human review. The same-researcher R reference contains 25 mentions of 15 people in 120 paragraphs from six reports, with two documented eligible mentions missing from the retained ledger. Office and affiliation accuracy has not been systematically validated, and the study does not establish measured labor or cost savings. Source links make evidence inspectable; they do not independently certify a claim's meaning or accuracy. See the [coverage denominators and interpretation limits](docs/research-workflow.md#evidence-coverage-and-validation-limits).

## Try the reusable toolkit

Use Python 3.12. No pip packages, model, API account, GPU, R, or LaTeX are needed for this example.

```console
git clone https://github.com/scott-kj/pkoc-research-explorer.git
cd pkoc-research-explorer
python tools/run_demo.py --output runs/demo
python tools/run_case.py validate --output runs/demo
```

The example uses **original fictional text and scripted local responses, not an LLM**. It exercises preparation, annotation stages, identity resolution, CAMEO coding, all three network scales, and explorer export. Expect three actors and one paragraph-scale edge with weight two, with an isolate retained. It makes no external calls. Read [the example description](examples/README.md).

Open the `index.html` path printed by the command, or load `runs/demo/bundle.json` through **Data & toolkit → Open local dataset** in the public explorer. Files stay in your browser.

For virtual environments, your own reports, local llama.cpp and compatible APIs, follow the **[step-by-step setup guide](docs/quickstart.md)**. Real inference requires explicit `--execute`, a provider profile, and a total request-attempt cap. Credentials stay in environment variables. Local runs, raw model responses, source reports and model files are ignored by Git.

| Path | Purpose |
|---|---|
| `tools/run_case.py` | Inventory, prepare, infer, network, export, validate, status and resumable run commands |
| `code/case_pipeline/` | Source checks, providers, grounding, identity resolution and annotation orchestration |
| `protocol/case_pipeline/` | Versioned prompts and response schemas |
| `protocol/codebook.json` | Actor coding rules and original explanations of CAMEO categories |
| `config/` | Editable case/provider examples and historical local-smoke settings |
| `examples/` | Fictional text and the explicitly scripted loopback demonstration |
| `web/` | Static explorer and evidence tables |

The toolkit automates a method, not factual certification. It preserves uncertainty, valid empty results, ambiguity, failures and coverage. New outputs are automated, without fabricated human-reviewed or reference branches. English extraction text is the v1 input; PDF extraction, OCR and multilingual processing are outside this implementation. Different models/providers do not guarantee equivalent or bitwise-identical results.

## Reproduce the public network views

Install Python 3.12 and Node.js 22. No Python or JavaScript packages are required for this static explorer.

```text
python tools/build_site.py --output site
python tools/verify_site.py site
node --test web/tests/core.test.cjs
node web/tests/check_bundle.cjs site/bundle.json
python -m http.server 8765 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8765/. The build destination must be new or empty. The site also includes a bootstrap bundle for direct local opening of index.html. All six native rosters, isolates, incidences and weighted edges are checked before publication. See the [bundle contract](docs/explorer-data-contract.md).

This repository executes the reusable annotation pipeline and reproduces network views from released annotations. The complete 1,000-draw statistical replay and manuscript build remain in the separate private research project. Recorded upstream verification is described in [verification](docs/verification.md); no new research or independent human validation is claimed. CI tests the public toolkit on Windows and Linux using controlled fixtures and makes no paid API calls.

## Attribution and publication scope

Original code is [MIT](LICENSE). Original annotations and written content are [CC BY 4.0](LICENSE-DATA.md), with [third-party exclusions](NOTICES.md). Cite [CITATION.cff](CITATION.cff), the repository commit and the downloaded bundle's SHA-256. The accompanying manuscript, *LLM-Assisted Annotation for Political Network Research: Evidence from UN Peacekeeping Reports*, remains unpublished; no DOI is asserted.

The source archive, complete report paragraphs, manuscript files, private annotation journals, participant/session records, model weights, API credentials and raw inference logs are not distributed here. Source rights for attributed annex material in S/2004/428 and S/2017/282 remain unresolved. This narrower structured-data publication does not clear or release those archives. See [the scoped review](docs/publication-review.md).

## Contact

Krerkkaiwan Kajohnkunchonlathorn · [Krerkkaiwan.k@cib.go.th](mailto:Krerkkaiwan.k@cib.go.th) · [LinkedIn](https://www.linkedin.com/in/police-major-krerkkaiwan-kajohnkunchonlathorn-872a91176/).

## Maintenance

This repository is the maintained home for the public explorer and reusable toolkit. The original private research repository remains the authority for the frozen UNMIL annotations. Update scientific data only through a new reviewed export and projection checks. Build scripts never refresh expected snapshot hashes automatically. The old private exporter must not overwrite newer public code. Presentation and software updates preserve the scientific snapshot unless explicitly reviewed.

GitHub Pages deploys only the generated site artifact. Repository history, source archives and the manuscript are never copied into that artifact. Pushes and pull requests run checks. To publish, manually run **Verify and publish explorer** from the Actions tab on main. Deployment requires explicit author authorization in publication.json and passing checks.
