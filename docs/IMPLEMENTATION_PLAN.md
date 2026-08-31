# Implementation plan

The September 1 date mentioned in the conversation is close enough that it should mean “reviewable internal alpha,” not a production launch. The safe immediate deliverable is this runnable scaffold, the discovery checklist, and a repeatable baseline; field reliance follows validation.

## Phase 0 — Discovery and baseline (2–3 focused sessions)

Deliverables:

- Inventory the three candidate laptops: exact CPU, RAM layout/ceiling, GPU/iGPU, VRAM, SSD, ports, OS, battery health, and supported acceleration backends.
- Capture the current Qwen3 8B runtime, quantization, prompt, context size, and timing.
- Convert 20–30 anonymized repairs into gold scenarios with expected safe next tests and unacceptable actions.
- Agree on the initial three diagnostic families and what “launch” means.
- Confirm case retention/deletion rules and whether voice is out of scope for alpha.

Exit criteria:

- A reproducible baseline score and latency report exists.
- The current laptop can run the selected baseline in airplane mode.
- Safety labels and the diagnostic response schema are accepted by the technician.

## Phase 1 — Thin vertical slice (week 1)

Deliverables:

- Local browser UI with create, list, open, and export case flows.
- SQLite persistence for observations, completed tests, and assessments.
- Replaceable model provider with mock and Ollama implementations.
- Schema-validated hypotheses and exactly one proposed next test.
- Deterministic duplicate-test guard.
- Risk validation and confirmation requirement for destructive work.

Exit criteria:

- A case can be started, worked, closed, resumed, and exported with the network disabled.
- Restarting the app loses no recorded test results.
- Unit tests cover duplicate and destructive-action behavior.

## Phase 2 — Grounded procedures (week 2)

Deliverables:

- Markdown procedure-card format with source URL, version, verification date, applicability, risk, prerequisites, and rollback metadata.
- SQLite FTS retrieval, local citations, and an import command.
- A curated starter bundle for the three pilot domains using redistributable material or local-only source files.
- Retrieval relevance tests and stale-source reporting.
- Optional semantic retrieval experiment only if FTS misses gold queries.

Exit criteria:

- Every surfaced command or OEM procedure can be traced to an indexed card.
- The application does not allow the model to cite a card it was not given.
- Knowledge can be rebuilt without internet access.

## Phase 3 — Field alpha (1–2 weeks of real work)

Deliverables:

- Installable, pinned offline bundle for the selected laptop.
- Airplane-mode smoke test and recovery instructions.
- Lightweight turn rating: useful/safe, correction, and optional note.
- Exported, anonymized evaluation traces.
- Weekly report for latency, next-test usefulness, repeats blocked, unsafe outputs, and retrieval misses.

Exit criteria:

- Josh completes representative real cases without needing cloud fallback for the core flow.
- Initial gold-set usefulness reaches 80% without a critical safety failure.
- The top failure patterns are categorized as model, prompt, retrieval, knowledge, or UI problems.

## Phase 4 — Optimize only from evidence

In order:

1. Improve case schema and prompts.
2. Improve or expand the knowledge cards.
3. Add hybrid retrieval/reranking if measured retrieval misses justify it.
4. Benchmark alternate quantized models on the actual laptops.
5. Consider LoRA/QLoRA only for repeated behavioral failures that remain after correct context and prompting.
6. Consider RAM, GPU, or eGPU upgrades only when the benchmark predicts a meaningful field improvement.

Voice, multimodal photos, command execution, multi-technician support, and commercial packaging each require a separate safety and product decision.

## Immediate backlog

| Priority | Item | Acceptance check |
| --- | --- | --- |
| P0 | Collect missing laptop specs | All candidates recorded in the benchmark sheet |
| P0 | Import 20 gold cases | No customer identifiers; expected next test and safety notes included |
| P0 | Validate the current scaffold with Josh | One real but anonymized case completed end to end |
| P0 | Benchmark Qwen3 8B baseline | Quality, first-token time, total time, and memory recorded |
| P1 | Compare current model candidates | Same prompts, context, cases, and scoring as baseline |
| P1 | Curate networking cards | Sources and risk metadata complete; retrieval checks pass |
| P1 | Add technician turn rating | Stored locally and included in evaluation export |
| P2 | Optional semantic retrieval | Adopt only if it fixes measured FTS misses |
| P2 | Windows packaging | One-click launcher plus offline recovery instructions |
