# Reusable PKOC annotation-to-network toolkit

`tools/run_case.py` processes explicitly selected English PKOC extraction texts into **model-only** annotations and three co-occurrence networks. The public software is separate from the frozen UNMIL analysis/manuscript implementation. UNMIL remains the documented research example. Start with [the setup guide](quickstart.md) and the original fictional example; no new research study is implied.

The toolkit automates a method, not factual certification. A processed response can be wrong. A compatible API is not evidence of identical schemas, reasoning, tokenization, seeds, or outputs across providers. Fresh inference is not claimed to be bitwise reproducible.

See [the research workflow](research-workflow.md), [the export contract](explorer-data-contract.md), [the data dictionary](data-dictionary.md), and [the explorer](https://scott-kj.github.io/pkoc-research-explorer/) for the historical study and reader-facing data.

## Inputs and explicit selection

Use Python 3.12. The public toolkit requires only the Python standard library. See [setup and examples](quickstart.md).

A [case profile](../config/cases/example.json) supplies a stable `case_id`, title, mission name and aliases, language, explicitly included/excluded document symbols and reasons, and cleaning settings. Mission references enter each prompt as supplied data. Catalog mission tags do not establish eligibility. For example, the UNAMSIL catalog contains addenda and a cross-border report; selecting the two engineering documents does not imply those other documents are generally ineligible.

The source directory contains existing English `_E.pdf.txt` or `_E.txt` PKOC extraction files. Actual files are found by document symbol. The catalog reader interprets duplicate `Document_ID` headers by position, uses the printed symbol rather than the unreliable filename column, and checks available mission/date metadata against the source header. Missing or duplicate matching files, conflicting headers, conflicting known catalog mission assignments, and inconsistent dates stop processing. An absent catalog row remains absent metadata. A profile date cannot invent finer precision than the source header/catalog: `2000`, `2000-01`, and `null` remain partial or unknown observations.

Only English extraction text is supported in v1. PDF extraction, OCR, multilingual processing, and historical PDF-extractor reconstruction are outside this tool. Newly downloaded PDFs cannot be assumed to reproduce the archived text bytes.

## Commands

| Command | Result | Inference requests |
|---|---|---|
| `inventory` | JSON inventory on stdout, including actual source hashes, header checks, selection reasons and exclusions | None |
| `prepare` | Own a new run directory; save inventory, canonical paragraphs, character maps and sentence boundaries | None |
| `infer` | Preflight by default; with `--execute`, produce the model-only ledger and private native receipts | Explicit only |
| `network` | Build three projections from an existing ledger | None |
| `export` | Build projections and a source-free explorer bundle, tables, GraphML and downloads | None |
| `validate` | Verify stored hashes, boundaries, grounding and projection; print scope-limited receipt | None |
| `status` | Show stage status, binding hash and completion/partial coverage | None |
| `run` | Preflight by default; with `--execute`, prepare → infer → network → export → validate | Explicit only |

`status` and `validate` need only `--output`. Status reports `lock_present` and `process_liveness=not_checked`: a present lock means `active_or_interrupted`, because the lock alone does not prove that its process is still alive. Saved stage outcomes remain visible. Unlocked preparation alone is `prepared`, and full-run `complete` requires complete inventory, preparation, inference, network, export and validation receipts; partial/failed inference is never promoted to full completion. `inventory` needs `--case`, `--sources`, and optionally `--catalog`. Other commands use the same case, provider, source, catalog, runtime-manifest and request-cap arguments throughout a run. After `prepare`, invoke subsequent stages with `--resume`. `infer` and `run` always require `--execute` to issue inference requests; without it they verify the supplied assets/configuration and report a preflight, without starting a model or creating a run.

Example PowerShell preparation using researcher-supplied paths:

```powershell
$caseArgs = @(
  '--case', 'local/case.json',
  '--provider', 'local/llama/provider.json',
  '--sources', $PkocExtractionDirectory,
  '--catalog', $PkocMetadataCsv,
  '--output', 'runs/my-case',
  '--model', $VerifiedGguf,
  '--server', $VerifiedLlamaServer,
  '--chat-template', $VerifiedChatTemplate,
  '--runtime-manifest', $VerifiedRuntimeManifest,
  '--max-requests', '100'
)
python tools/run_case.py inventory --case local/case.json --sources $PkocExtractionDirectory --catalog $PkocMetadataCsv
python tools/run_case.py run @caseArgs
# Explicit execution, after inspecting the preflight:
python tools/run_case.py run @caseArgs --execute
python tools/run_case.py status --output runs/my-case
python tools/run_case.py validate --output runs/my-case
# Interrupted/partial work may be resumed only with the identical binding and cap:
python tools/run_case.py run @caseArgs --execute --resume
```

The command above uses the reports explicitly selected in your local case profile. The cap is **100 total inference attempts**, including retries and interrupted calls; it is not 100 successful responses. Health, model-list, local template-rendering and tokenization calls are preflight operations and separately identified. A cap exhausted run produces a `partial` receipt and any available model-only network; the command returns exit code 2. Failed stages can yield `complete_with_failures`, also exit code 2. There is no automatic budget expansion. Change inputs, code, settings, or the cap only by starting a separately owned new run.

## Run ownership and artifacts

A destination must be new or empty. A populated destination requires `--resume`, an owned `run-state.json`, and exact agreement of case/provider settings, selected input hashes, catalog hash, runtime manifest hash, request cap, and executed code/prompt hashes. Symlink/junction output paths and their ancestors are rejected. Inside this repository, runs must live under ignored `runs/`; source archives and output directories must not overlap. A run lock prevents simultaneous writers.

Each run contains:

- `inventory.json`: symbol-to-file mapping, original byte hashes, dates and selection decisions.
- `prepared.json`: **private local source text**, paragraph boundaries, codepoint source maps, sentence spans and cleaning counts.
- `ledger.json`: **private local** raw extraction anchors, model identity decisions, coverage and the derived L ledger.
- `private/requests/*.start.json` and `*.finish.json`: immutable native payloads/responses, generation and token receipts, usage, validation outcomes and elapsed time. A durable attempt reservation in run-state is saved before the start file or POST and consumes budget even when a crash prevents the start/finish receipt. Deleting indexed receipts cannot restore budget; missing or orphan receipts fail validation. A reserved-but-unwritten start and a finish written immediately before its registry update are explicit recoverable crash boundaries.
- `private/runtime-verification.json`, `private/provider-receipt.json`, `private/server/`: verified local assets or API identity/capability information, process lifecycle and local logs. Credentials are environment-only and redacted from native receipts.
- `bundle.json`: a publication-oriented allowlisted export without full paragraphs, raw inference logs, private paths, model reasons or credentials.
- `exports/<bundle-hash>/`: immutable bundle-specific explorer, CSV/JSON tables, GraphML, checksums and download package.
- `validation.json`: current run verification with its actual inputs, status and limits. It does not replace historical UNMIL receipts.

The entire run remains private. A source-free bundle is not automatically licensed for publication; rights review and separate publication instructions still apply. Original code uses MIT; original annotations/documentation use CC BY 4.0 subject to the repository's third-party exclusions. Consult `LICENSE`, `NOTICES.md` and `CITATION.cff` before redistribution. API execution transmits the supplied source packets to the explicitly selected endpoint; the static explorer never does so.

## Cleaning and canonical coordinates

The implementation reuses portable `corpus.py` mapped normalization/cleaning functions and `segmentation.py`, not a private legacy revision chain. Numbered mode selects the deterministic longest numbered paragraph chain, removes standalone document/page/production artifacts, normalizes Unicode with NFKC and the recorded apostrophe/dash mappings, joins whitespace and optionally stops at a literal annex heading. Extra stop headings must be explicit profile strings; no UNMIL-specific force-strength heading is installed as a general default. Blankline parsing requires explicit selection rather than silent fallback. A paragraph limit is an explicit engineering sampling control and records the number excluded.

Inventory and preparation parse and hash the same captured source bytes, then reject changed source snapshots before export. Each canonical codepoint retains its raw extraction codepoint span. Normalization can map several original characters to one canonical character or one original character to several canonical characters; inserted join spaces map to the source gap. `prepared.json` supports before/after inspection through `raw_start`, `raw_end`, `source_codepoint_spans`, original source hashes and canonical text hashes. These are Unicode codepoint offsets, not UTF-8 bytes or JavaScript UTF-16 code units. Sentence boundaries are paragraph-local, zero-based, half-open and deterministic.

## Model stages and uncertainty

1. **Mention extraction.** Report-bounded batches contain up to four complete paragraphs and 6,500 characters. Names are copied literally with optional immediately adjacent left/right anchors. Python grounds only a unique exact match. Repeated text without sufficient anchors remains ambiguous; fuzzy normalization, selecting the first match, and fabricating offsets are forbidden. Valid empty responses are `processed_empty`; abstention, failure, unprocessed input and context exclusion remain distinguishable.
2. **Identity resolution.** The portable retrieval policy considers normalized equality collisions and at most five non-equality candidates using string/token evidence. The model independently evaluates each candidate from quoted context. Exactly one supported SAME link may attach an occurrence; multiple SAME links or conflicts remain unresolved. A long personal-name form can create a new anchor only when no candidate exists or all retrieved candidates are explicitly DIFFERENT. Short forms and insufficient evidence stay unresolved. Names alone never force transitive merges.
3. **Offices and affiliations.** Each resolved actor/report is evaluated with its own occurrence anchors and source paragraphs. Literal role, office and affiliation fields must occur contiguously in cited evidence. Current/former/future/unspecified capacity is preserved. Report dates are observations, not tenure boundaries, continuous presence or inferred absence.
4. **CAMEO actor coding.** The complete existing 28-code actor-sector dictionary is supplied with the original evidence and literal claims. This is actor coding, not event coding. Assignments must echo the literal fields and preserve role codes, specialty codes and their union separately. Unsupported/conflicting/out-of-scope assignments have empty code arrays. The dictionary's project adaptations and international exclusions remain explicit. A valid schema or existing citation does not prove substantive support.

The new pipeline does not import the historical UNMIL first-SAME behavior, Bryant supplements, amendment token windows, saved human interventions or dependent-reference decisions as general defaults. It creates **L only**, marked `model-only` and `human_reviewed=false`; it never fabricates A or R. Technical failures may receive one identical-request retry (maximum two attempts); mechanically valid empty results and abstentions are terminal. Native duplicate predictions are retained in the private ledger, then deduplicated for the analytical export. Ambiguous/unresolved occurrences remain visible with null actor IDs and are excluded from network projection with counts.

## Providers and execution limits

The [historical local profile](../config/providers/llama-local.json) preserves the recorded checkpoint/template hashes, llama.cpp build, seed, temperature, GPU/CPU settings and per-stage budgets. It verifies a `pkoc-runtime-v1` JSON allowlist of `{file, sha256}` members relative to the server directory, checks every supplied member, and rejects unlisted executable/library dependencies. Historical nonbinary lock receipts are untouched; archived distribution files are not treated as loaded libraries. Build the allowlist from a trusted, independently verified release archive, not an unverified downloaded binary. Weights, runtime DLLs and proprietary assets remain outside Git.

The adapter launches and owns the verified server with an explicit loopback address, allocated port, model, template, one inference slot and process log. It does not attach to an existing unknown service. A fresh random API key is passed only through the child process environment and kept in adapter memory; inherited llama settings are removed, the Web UI is disabled, and CORS is restricted to localhost. The key is never placed in a command line or receipt. It checks health and advertised model identity, renders the full chat template and tokenizes it before generation, and terminates only its own process. See the [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) for the upstream API; the pinned runtime and receipts govern this implementation.

The [compatible-API example](../config/providers/compatible-api.example.json) is deliberately nonoperational until the researcher supplies an endpoint/model and confirms capabilities. Credentials come only from the named environment variable. Remote endpoints require HTTPS; loopback HTTP is allowed for local compatible servers and controlled fixtures. Redirects, URL credentials and query-string secrets are rejected. The model must be advertised by `/models`. JSON schema support is required; seed and thinking parameters are emitted only when explicitly supported. The supported thinking parameter mapping is `chat_template_kwargs.enable_thinking`; unsupported mappings stop before calls.

For APIs without llama tokenization, the operator must declare a conservative UTF-8-byte token upper bound and chat overhead appropriate to that provider. Receipts label this as `operator-declared-upper-bound`, never as measured tokenizer identity. Unsupported capability declarations are rejected. Context-overflow packets are excluded with receipts rather than silently truncated; increase limits only in a new run with documented provider support. No provider fallback, prompt repair, hidden retry, model download or automatic paid API execution occurs.

The case profile also declares a conservative `literal_policy`: by default names are at most 160 Unicode codepoints and role/office/affiliation literals at most 400. These limits are researcher-configurable (positive integers up to 4,000), are bound in the run configuration, and are not claims about universally valid name/title lengths. Regardless of configured length, a source-derived field containing any complete selected canonical paragraph is rejected. Extraction and office validation apply the rule before acceptance, and the publication export checks surfaces, names, aliases and literal claim fields again. Violations become bounded failed predictions with visible coverage/exclusion status; the toolkit never truncates them into apparent valid annotations. This conservative policy may exclude a genuine unusually long name/title or a paragraph consisting only of a name.

## Network and explorer contract

For each sentence, paragraph or report, repeated occurrences of one actor count as binary presence. With unit-by-actor incidence matrix `B`, `W = BᵀB` and the diagonal is removed. Edges are undirected weighted **co-occurrence**, not interaction or alliance. Native resolved actors are retained as isolates by default. Unresolved identities, absent unit assignments and selection exclusions are counted explicitly. Missing dates do not remove otherwise grounded observations from report/paragraph/sentence networks; they remain unknown in year views.

The shared `explorer_data.project_network` implementation produces nodes, weighted edges, supporting unit IDs and incidences; `write_bundle` exports CSV, JSON, GraphML and the static explorer. Loading another compatible bundle happens entirely in the browser. Optional local source loading accepts private `prepared.json`, verifies paragraph hashes against the source-free bundle, and highlights Unicode codepoint spans without uploading text. Study controls rebuild transparent exploratory projections; there is no annotation editor or automatic scientific-result replacement.

## Verification

Run the focused engineering suite:

```console
python -m unittest discover -s code -p "test_case_pipeline*.py" -v
```

The suite uses fictional text and controlled loopback HTTP servers, including a mocked owned-process boundary around the real local-adapter HTTP routes. It tests duplicate metadata headers, erroneous filenames, mission/header/date conflicts, partial dates, Unicode maps/grounding, duplicate names, ambiguous identities, empty and failed responses, unsupported capabilities, request caps, interrupted starts, resume hashes, separate runs and source-free exports. It does not claim GPU execution from a mocked process. The historical private-project local-model smoke retains its original runtime/request scope. This public release validates controlled HTTP fixtures and the scripted fictional example; it does not rerun a real model or claim new model-accuracy evidence. Full frozen-study replay, source reconstruction and manuscript-build checks remain in the original verification workflow.


## Public software maintenance

The public checkout maintains the reusable toolkit independently of the historical manuscript package. Versioned prompts and schemas are original project code; the CAMEO actor identifiers are attributed in `protocol/codebook.json`, with project coding decisions kept explicit. The fictional example is marked `synthetic_fixture: true`, suppresses official source links and declares that its replies are scripted. Actual report profiles must omit this flag. Changing code or profile contents requires a new run because the resume binding records the executed implementation.
