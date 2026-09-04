# Architecture

## Overview

```text
Local browser UI
      |
FastAPI on 127.0.0.1
      |
Diagnostic service ---------------- Safety and repeat guards
   |          |          |
SQLite     Retriever   Model provider
cases      SQLite FTS  Ollama, llama.cpp, or mock
                |
       Curated procedure cards
```

The application binds to localhost and stores all mutable data under `FIELDTECH_DATA_DIR`. Model inference is performed by a local runtime: separately installed Ollama for the Full profile or the bundled, API-key-protected llama.cpp process for Field Kit Lite. The provider boundary prevents the case logic and UI from depending on one model or inference engine.

## Diagnostic turn

1. The API invalidates the current action, then atomically records a new observation or the result of the currently proposed test or intervention.
2. The service builds a compact case snapshot from structured state, not the raw chat transcript alone.
3. The retriever searches the local procedure index using the complaint, latest input, and active hypothesis terms.
4. Only the top retrieved cards and their IDs enter model context.
5. The model must return a JSON-schema-valid assessment with ranked hypotheses, one next test or one intervention, evidence, a technician-facing explanation, and cited card IDs.
6. The service removes unknown citations, checks the proposed action against completed work, and applies deterministic storage, BitLocker, network, power, and risk guards.
7. A guard rejection is recorded and may receive one bounded repair attempt through the same guards. Provider, timeout, and schema failures are never retried.
8. The validated assessment and an immutable event are atomically persisted before the API responds.

## State ownership

The model may propose state, but it never owns state. SQLite records:

- Case identity, complaint, device context, status, and timestamps
- Technician observations
- Proposed and completed tests and interventions, including natural-language results
- Each validated diagnostic assessment
- Confirmation records for risky interventions
- Export metadata

The current assessment can be replaced; the event history is append-only. This makes failures inspectable and allows future replay against a different model.

## Knowledge retrieval

The first implementation uses SQLite FTS5 because it is small, transparent, and works offline without a second model. Procedure cards are Markdown plus YAML metadata. Strong diagnostic signals can select multiple compatible cards by stable ID; ambiguous cases fall back to FTS. Retrieval is capped at four cards and the serialized knowledge context is capped at 9,000 characters.

Semantic embeddings and reranking are an experiment, not a prerequisite. Add them behind the retriever interface only if gold-query evaluation shows meaningful misses. An embedding index must be versioned with the exact embedding model and rebuildable from the source cards.

## Model interface

The Full-profile adapter uses Ollama's local `/api/chat` endpoint with a JSON schema. Field Kit Lite uses llama.cpp's OpenAI-compatible loopback endpoint, schema-constrained output, a random port, and an in-memory per-session API key. Both responses are validated again with Pydantic. A mock provider makes the UI, persistence, safety behavior, and tests runnable without a diagnostic model.

The implemented llama.cpp adapter also works with LM Studio's local
OpenAI-compatible endpoint for full-model evaluation. Runtime-specific timing
fields are optional; the benchmark records them when exposed without making
inference depend on a particular server version.

## Safety boundary

The MVP never executes commands. Each proposed test or intervention carries one of three risk levels:

- `safe`: observational or easily reversible
- `caution`: meaningful side effects or elevated privileges
- `destructive`: possible data loss, irreversible change, or high operational impact

Anything marked destructive must include prerequisites, a backup/rollback statement, and `requires_confirmation=true`. Every non-safe intervention must also include prerequisites, rollback, and confirmation. BitLocker unlock or customer-data access is always a `caution` intervention with authorization and matching key-ID prerequisites. The API refuses an invalid proposal. A future command runner would be a separate privileged component and is explicitly outside this architecture.

## Privacy boundary

- Bind only to loopback unless a future authenticated design is implemented.
- No telemetry, cloud fallback, or remote model URL by default.
- Do not put names, credentials, license keys, email contents, or unrelated customer files in prompts.
- Reject BitLocker recovery keys before they can enter case storage, prompts, results, or exports; the customer enters a matching key privately in the trusted Windows prompt.
- Rely on OS full-disk encryption for the alpha; define app-level encryption before multi-user or sensitive long-term retention.
- Support explicit case deletion and retention settings before field deployment.

## Failure behavior

- Before model work starts, any prior test or intervention is invalidated and persisted. A timeout or provider failure cannot leave a stale action available for submission.
- If the model is unavailable, the recorded observation/result remains saved, the assessment exposes no action, and the UI reports the failure.
- Invalid model JSON is rejected; it is never partially applied.
- Unknown citations are discarded before the assessment is presented or persisted.
- A repeated test requires a specific material-change rationale; otherwise the turn fails closed and may receive one audited repair attempt within the configured budget.
- Completion writes use optimistic concurrency so duplicate submissions cannot both succeed.
- If no safe next step exists, the model can return `insufficient_evidence` or recommend escalation.
