# PKOC Research Explorer

Explore how annotations become political co-occurrence networks, using the frozen UNMIL research example by Krerkkaiwan Kajohnkunchonlathorn.

**Website:** https://scott-kj.github.io/pkoc-research-explorer/

Author publication authorization and the exact reviewed dataset are recorded in [publication.json](publication.json).

## Explore and download

- Follow the [research workflow](docs/research-workflow.md) from report checks and cleaning to annotation, identity resolution and network projection.
- Search actor × year observations, inspect actor records and examine the distinct units supporting each edge.
- Switch L/A and sentence/paragraph/report contexts. Reset to the complete UNMIL paper preset. R has its own limited reference-audit view.
- Download annotations, actor and edge tables, incidence lists, GraphML and view settings.
- Load compatible JSON bundles or verified source text locally. The application does not upload these files or request API credentials.

Year cells count observations in published reports; blanks do not establish absence or tenure. Edges represent undirected co-occurrence, not interactions or alliances. The [data dictionary](docs/data-dictionary.md) explains identity, uncertainty, human decisions and source support.

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

This repository reproduces network views from released structured annotations. The complete 1,000-draw statistical replay, manuscript build and reusable inference CLI remain in the separately maintained research project. They are not executable from this smaller website repository. Recorded upstream verification is described in [verification](docs/verification.md); no new research or independent human validation is claimed.

## Attribution and publication scope

Original code is [MIT](LICENSE). Original annotations and written content are [CC BY 4.0](LICENSE-DATA.md), with [third-party exclusions](NOTICES.md). Cite [CITATION.cff](CITATION.cff), the repository commit and the downloaded bundle's SHA-256. The accompanying manuscript, *LLM-Assisted Annotation for Political Network Research: Evidence from UN Peacekeeping Reports*, remains unpublished; no DOI is asserted.

The source archive, complete report paragraphs, manuscript files, private annotation journals, participant/session records, model weights, API credentials and raw inference logs are not distributed here. Source rights for attributed annex material in S/2004/428 and S/2017/282 remain unresolved. This narrower structured-data publication does not clear or release those archives. See [the scoped review](docs/publication-review.md).

## Maintenance

The original research repository remains the authority for UNMIL annotations. This site is a reviewed distribution of a frozen snapshot, not an annotation editor. Update scientific data only by importing a new reviewed export, documenting the change and rerunning projection checks. Build scripts never refresh expected snapshot hashes automatically. Public-site presentation and documentation changes belong here and must preserve the scientific snapshot unless explicitly reviewed.

GitHub Pages deploys only the generated site artifact. Repository history, source archives and the manuscript are never copied into that artifact. Pushes and pull requests run checks. To publish, manually run **Verify and publish explorer** from the Actions tab on main. Deployment requires explicit author authorization in publication.json and passing checks.
