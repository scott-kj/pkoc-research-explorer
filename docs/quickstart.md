# Run the PKOC annotation-to-network toolkit

Start with the fictional example, then supply your English PKOC extraction text and a model provider. The CLI creates automated annotations and sentence, paragraph, and report co-occurrence networks. It does not create human-reviewed annotations.

## 1. Get the code

Install Python 3.12 and Git. The toolkit uses Python's standard library; there are no pip dependencies. Node.js 22 is needed only for the optional JavaScript tests. You do not need R, LaTeX, a GPU, or a model to run the fictional example.

```console
git clone https://github.com/scott-kj/pkoc-research-explorer.git
cd pkoc-research-explorer
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe tools/run_demo.py --output runs/demo
.\.venv\Scripts\python.exe tools/run_case.py validate --output runs/demo
```

Linux/macOS:

```sh
python3.12 -m venv .venv
.venv/bin/python tools/run_demo.py --output runs/demo
.venv/bin/python tools/run_case.py validate --output runs/demo
```

Use your environment's Python executable for the `python` commands below. Virtual-environment activation is optional. Windows and Linux are checked in CI; macOS uses the same standard-library code but is not a separate CI target.

The demo runs the complete pipeline against a **scripted loopback fixture, not an LLM**. It uses original fictional passages, makes no external calls, and costs nothing. Expect five paragraphs, three actors, and one paragraph-scale edge with weight two. Read the [example description](../examples/README.md).

Open the printed `index.html` path. Alternatively, visit the [public explorer](https://scott-kj.github.io/pkoc-research-explorer/), choose **Data & toolkit → Open local dataset**, and select `runs/demo/bundle.json`. Files are read locally in your browser. Select `prepared.json` with **Add local source text** to inspect the fictional evidence. For a second demonstration, choose a new output such as `runs/demo-2`; existing results are never overwritten.

## 2. Select your own reports

Use existing **English extraction text**, named like `S_2000_13_E.pdf.txt` or `S_2000_13_E.txt`. Keep it outside the repository or in ignored `local-sources/`. The tool does not download reports, extract PDFs, perform OCR, or translate documents.

Copy `config/cases/example.json` to `local/case.json` after creating the ignored `local/` directory. Edit:

- `case_id` and `title`: your run's identity and descriptive title.
- `mission`: the mission's name and aliases, with language `en`.
- `documents`: explicit document symbols, inclusion decisions and reasons. Keep dates `null` if unknown; partial dates are allowed. Known dates must agree with headers/catalog metadata.
- `cleaning`: numbered paragraphs or explicitly chosen blank-line mode, annex handling, additional stop headings, and an optional small paragraph limit for a pilot.

The fictional demo's `synthetic_fixture` flag must **not** be used for actual reports. An optional PKOC catalog can be supplied with `--catalog local/metadata.csv`. The parser checks symbols and available metadata against the actual files; a mission tag alone does not establish eligibility.

```console
python tools/run_case.py inventory --case local/case.json --sources local-sources
```

Review the selected documents before model execution. Missing, ambiguous or inconsistent source matches stop processing. See [cleaning and coordinate rules](toolkit.md#cleaning-and-canonical-coordinates).

## 3A. Use a compatible API

Copy `config/providers/compatible-api.example.json` to `local/provider.json`. Set the endpoint (for example your provider's documented `/v1` base), advertised model ID, context limits and capability declarations. The supplied `.invalid` endpoint is deliberately nonoperational.

The server must expose `/models` and `/chat/completions` and support the supplied JSON schemas. Compatibility alone does not establish that seed, reasoning controls, or tokenizer bounds behave identically. Read [provider requirements](toolkit.md#providers-and-execution-limits) before setting these fields.

Supply the API key through the profile's named environment variable, `PKOC_API_KEY`. Use your normal local secret manager or environment configuration; do not add keys to JSON profiles, reports, source control, or command arguments. API execution sends selected source passages to the endpoint you configure.

First perform a dry run. This checks local configuration and inputs without contacting the provider or creating a run:

```console
python tools/run_case.py run --case local/case.json --provider local/provider.json --sources local-sources --output runs/my-case --max-requests 100
```

After reviewing the setup and your provider's costs, opt in explicitly:

```console
python tools/run_case.py run --case local/case.json --provider local/provider.json --sources local-sources --output runs/my-case --max-requests 100 --execute
```

`--max-requests` caps total inference attempts, including failed calls and retries; it is not a monetary or token budget. Per-stage `max_tokens` and context ceilings are declared in the provider profile. Check your provider's pricing and limits separately. No automatic provider fallback or budget expansion occurs.

## 3B. Use local llama.cpp

Obtain and independently verify a llama.cpp runtime, a compatible GGUF model, and its Jinja chat template. They stay outside Git. Follow the [official server documentation](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) for runtime requirements. This adapter requires `/apply-template`, `/tokenize`, schema-constrained chat completions, and the launch flags documented in the toolkit guide; arbitrary older builds are not assumed compatible.

Place the runtime executable and libraries in a dedicated directory. Record a profile using your paths; the following is a single command shown over lines for readability (use one line in PowerShell):

```sh
python tools/configure_local.py --server /path/to/runtime/llama-server --model /path/to/model.gguf --chat-template /path/to/template.jinja --model-id my-pkoc-model --engine-build "your independently verified build" --output local/llama --gpu-layers 0 --threads 4
```

On Windows, pass paths to `llama-server.exe`, the GGUF, and the template; quote paths containing spaces. The helper records hashes and creates `local/llama/provider.json` and `local/llama/runtime.json`. It does not authenticate a download, fetch a model, or launch software. Confirm the generated profile's context limits and supported options before use. Its default is CPU execution; choose GPU layers appropriate to your hardware. No universal RAM/VRAM requirement is claimed because it depends on the model and context size.

```console
python tools/run_case.py run --case local/case.json --provider local/llama/provider.json --sources local-sources --output runs/my-local-case --model /path/to/model.gguf --server /path/to/runtime/llama-server --chat-template /path/to/template.jinja --runtime-manifest local/llama/runtime.json --max-requests 100
```

Inspect the preflight, then repeat that command with `--execute`. The tool starts its own loopback-only server and stops that process afterward. `config/providers/llama-local.json` retains the historical engineering-smoke settings as a reference; it is not a promise that those assets exist on another machine or that a different model reproduces the study.

## 4. Inspect, resume and explore

```console
python tools/run_case.py status --output runs/my-case
python tools/run_case.py validate --output runs/my-case
```

To resume an interrupted run, repeat its original command with `--resume --execute`, keeping inputs, profile contents, code, runtime assets and request cap unchanged. A changed configuration requires a new run directory. If a lock remains after interruption, inspect the process state before removing it; the mere presence of a lock does not prove a process is running.

Exit `0` means the command completed within its reported scope. Exit `2` means partial/interrupted inference or completion with failures. Exit `1` signals an error. A preparation-only command or successful integrity check does not establish complete inference or factual accuracy.

The run includes `bundle.json`, private `prepared.json`/`ledger.json`, native request receipts, validation records, and `exports/<bundle-id>/` containing the local explorer, CSV, JSON, GraphML and a download archive. Load `bundle.json` in the public explorer; the application never requests model credentials.

All `runs/` and `local/` contents are ignored by Git. Assess annotation quality, coverage, confidentiality and source rights before sharing any result. The software release does not grant permission to redistribute reports or raw API logs.

## Troubleshooting and tests

| Result | What to check |
|---|---|
| No unique source match | Match the exact document symbol to one English extraction filename; remove ambiguous duplicate inputs from your selection. |
| Header or date mismatch | Resolve the input/catalog discrepancy; do not invent missing date components. |
| Unsupported capability/model | Check the actual server's advertised model, schema support, thinking mapping and context settings. |
| Partial or failed calls | Read `status`, coverage and local receipts. Keep partial findings visibly partial. |
| Resume binding differs | Restore the original inputs/settings, or choose a new run directory. |
| Local runtime exits | Inspect the private server log and compare its CLI flags, template and hardware settings with your verified build. |

```console
python -m unittest discover -s code -p "test_case_pipeline*.py" -v
python -m unittest discover -s tools -p "test_toolkit_public.py" -v
```

For the study's framework, read [the research workflow](research-workflow.md). For stage contracts, provider limitations and output fields, read [the complete toolkit guide](toolkit.md) and [data dictionary](data-dictionary.md).
