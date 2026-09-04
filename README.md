# Field Tech Copilot

[Download the Windows Field Kit](https://ben4mn.github.io/field-tech-copilot/) · [Release notes](https://github.com/ben4mn/field-tech-copilot/releases) · [Windows distribution guide](docs/WINDOWS_DISTRIBUTION.md)

Field Tech Copilot is an offline-first diagnostic case notebook for computer repair work in places with unreliable connectivity. A technician describes the complaint, records observations and test results, and gets one evidence-based next test at a time. The application keeps diagnostic state outside the chat transcript, prevents accidental repeat testing, and grounds procedures in a curated local knowledge bundle.

This repository is an early MVP foundation. It is decision support for a trained technician, not an autonomous repair tool. It does not execute commands, change customer systems, or guarantee a diagnosis.

## What the MVP does

- Runs as a local browser application bound to `127.0.0.1`.
- Saves and resumes cases in a local SQLite database.
- Tracks the complaint, observations, completed tests and interventions, results, and ranked hypotheses.
- Proposes exactly one next-best test or controlled intervention and explains why it is useful.
- Rejects repeat tests unless the model provides a specific reason to repeat one.
- Invalidates stale actions before new evidence or model work, and fails closed on timeouts or invalid output.
- Allows one bounded, audited repair attempt after a deterministic guard rejection; provider failures are not retried.
- Requires prerequisites, rollback, and technician confirmation for non-safe interventions.
- Rejects BitLocker recovery keys from case storage and prompts the customer to enter them privately.
- Retrieves a bounded set of locally indexed procedure cards and only exposes citations that were actually retrieved.
- Exports a concise Markdown case summary.
- Supports a mock model for development, Ollama for a larger local model, and a
  protected llama.cpp adapter for the bundled Windows Field Kit Lite.

## One-click Windows field kit

The GitHub Pages download site offers a single Windows x64 installer built from
this repository. Field Kit Lite bundles:

- the application and its Python runtime;
- a pinned llama.cpp CPU runtime;
- the official Apache-2.0 Qwen3-1.7B Q8_0 GGUF;
- synthetic starter knowledge, the 16-card field procedure pack, and third-party license files; and
- a release checksum and machine-readable bundle manifest.

After the installer is downloaded, setup and the core case workflow do not need
an internet connection. The desktop launcher stores cases under
`%LOCALAPPDATA%\FieldTechCopilot`, starts the model on a random loopback port
with a per-session API key, opens the browser UI, and shuts the child runtime
down when the app is quit.

Field Kit Lite is deliberately small enough to fit GitHub's per-asset limit. Its
1.7B model is useful for evaluating the workflow but is **not validated for
field diagnosis**. Treat every result as untrusted decision support.

Initial requirements: Windows 10 22H2 or Windows 11, x64 CPU, 8 GB RAM, and
6 GB free disk space. Preview builds are unsigned unless the release shows a
trusted Windows publisher; SmartScreen or organization policy may block an
unsigned build.

## Quick start

Prerequisites for source development: Python 3.11+,
[uv](https://docs.astral.sh/uv/), and optionally
[Ollama](https://docs.ollama.com/) with a local model downloaded before going
offline.

```bash
uv sync --extra dev
cp .env.example .env
uv run fieldtech knowledge ingest examples/knowledge
uv run fieldtech serve --provider mock
```

Open <http://127.0.0.1:8765>. The mock provider lets you exercise the workflow without downloading a model.

For local model inference:

```bash
ollama pull qwen3:8b
ollama serve
uv run fieldtech serve --provider ollama --model qwen3:8b
```

### Full local AI profile

The model is deliberately configurable. Keep Qwen3 8B as the fallback and
comparison control. On the tested 64 GB dual-channel Latitude 5550,
Qwen3-30B-A3B Q4_K_M is the quality candidate, but it must be compared through
the repository benchmark before promotion on another machine. This profile
requires a separate model download before going offline and is not part of the
one-file Lite installer.

## Commands

```bash
# Start the local application
uv run fieldtech serve

# Import Markdown procedure cards into the local full-text index
uv run fieldtech knowledge ingest ./path/to/knowledge

# Verify the database, model runtime, and airplane-mode readiness
uv run fieldtech doctor

# Run the test suite
uv run pytest
```

Run the synthetic seven-case benchmark with the configured real provider. This
PowerShell example uses LM Studio; replace the identity values with the exact
local artifacts:

```powershell
$env:FIELDTECH_MODEL_PROVIDER = "llama_cpp"
$env:FIELDTECH_MODEL_BASE_URL = "http://127.0.0.1:1234/v1"
$env:FIELDTECH_MODEL_NAME = "qwen/qwen3-30b-a3b-2507"
$env:FIELDTECH_MODEL_TIMEOUT_SECONDS = "300"
$env:FIELDTECH_MODEL_REASONING_EFFORT = "low"
uv run python scripts/benchmark_cases.py `
  examples/gold-cases/qwen30b-field-suite.yaml `
  --output "$env:TEMP\fieldtech-warm.jsonl" `
  --run-kind warm `
  --runtime-version "LM Studio <exact-version>" `
  --model-sha256 "<exact-64-character-SHA256>" `
  --strict
```

The benchmark refuses an accidental mock-provider run. A cold sample is one
freshly unloaded/restarted model request and therefore requires one `--case-id`
plus a truthful `--cold-start-method`; see [the evaluation plan](docs/EVALUATION.md).

Configuration is read from `FIELDTECH_*` environment variables; see [.env.example](.env.example). The application never reads `.env` by itself, so use your shell, a launcher, or `uv run --env-file .env ...` to load it.

## Project map

```text
src/fieldtech/
  api/          local HTTP API and zero-build browser UI
  core/         case models, persistence, safety, and diagnostic orchestration
  knowledge/    procedure-card parsing and SQLite FTS retrieval
  providers/    replaceable local model adapters
docs/           discovery analysis, architecture, safety, and delivery plan
examples/       synthetic knowledge cards and gold cases
tests/          deterministic unit and API tests
site/           static GitHub Pages download site
packaging/      reproducible Windows bundle and installer definitions
```

Start with [the implementation plan](docs/IMPLEMENTATION_PLAN.md), [product brief](docs/PRODUCT_BRIEF.md), [architecture](docs/ARCHITECTURE.md), and [model/runtime benchmark plan](docs/MODEL_AND_RUNTIME.md).

## Privacy and repository hygiene

Customer data, real repair transcripts, local databases, model files, generated
embeddings, and licensed vendor manuals must not be committed. The source
conversation and personal contact information are intentionally excluded. Use
synthetic or fully anonymized examples only.

Original project code is source-available under [the repository license](LICENSE).
Bundled third-party components retain their own terms; see
[the third-party notices](THIRD_PARTY_NOTICES.md).
