# Field Tech Copilot

Field Tech Copilot is an offline-first diagnostic case notebook for computer repair work in places with unreliable connectivity. A technician describes the complaint, records observations and test results, and gets one evidence-based next test at a time. The application keeps diagnostic state outside the chat transcript, prevents accidental repeat testing, and grounds procedures in a curated local knowledge bundle.

This repository is an early MVP foundation. It is decision support for a trained technician, not an autonomous repair tool. It does not execute commands, change customer systems, or guarantee a diagnosis.

## What the MVP does

- Runs as a local browser application bound to `127.0.0.1`.
- Saves and resumes cases in a local SQLite database.
- Tracks the complaint, observations, completed tests, results, and ranked hypotheses.
- Proposes exactly one next-best test and explains why it is useful.
- Rejects repeat tests unless the model provides a specific reason to repeat one.
- Requires warnings and technician confirmation for destructive or data-risking procedures.
- Retrieves locally indexed procedure cards and only exposes citations that were actually retrieved.
- Exports a concise Markdown case summary.
- Supports a mock model for development and an Ollama adapter for fully local inference.

## Quick start

Prerequisites: Python 3.11+, [uv](https://docs.astral.sh/uv/), and optionally [Ollama](https://docs.ollama.com/) with a local model downloaded before going offline.

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

The model is deliberately configurable. Keep the existing Qwen3 8B setup as the baseline and benchmark alternatives against the same gold cases before changing hardware or committing to a model.

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
```

Start with [the implementation plan](docs/IMPLEMENTATION_PLAN.md), [product brief](docs/PRODUCT_BRIEF.md), [architecture](docs/ARCHITECTURE.md), and [model/runtime benchmark plan](docs/MODEL_AND_RUNTIME.md).

## Privacy and repository hygiene

Customer data, real repair transcripts, local databases, model files, generated embeddings, and licensed vendor manuals must not be committed. The source Discord conversation and personal contact information are intentionally excluded. Use synthetic or fully anonymized examples only.

No license has been selected yet. Until ownership and distribution are agreed, treat this repository as private and all rights reserved.
