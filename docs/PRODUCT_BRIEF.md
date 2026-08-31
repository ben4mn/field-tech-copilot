# Product brief

## Problem

Field computer repair work often happens where cloud assistants are unavailable. A technician needs help organizing ambiguous symptoms and choosing discriminating tests, but a normal chat assistant can forget prior work, repeat advice, invent commands, or jump to a repair before enough evidence exists.

## Product promise

Field Tech Copilot keeps the diagnostic thread intact offline. It helps a technician decide what to test next, explains why, and grounds risky procedures in a versioned local knowledge base while leaving every action under human control.

## MVP user story

> As a field technician without reliable internet, I can start a case from a customer's complaint, record observations and test results in normal language, and receive one safe, useful next test without losing or repeating prior work, so I can reach a supported intervention faster.

## MVP scope

The field pilot should cover three diagnostic families:

1. Networking, Wi-Fi, and connectivity
2. Windows boot, update, and performance problems
3. Printers and network printers

The system will provide a local web UI, persistent cases, structured assessments, one next test, local citations, safety gates, save/resume, and Markdown export.

## Explicit non-goals for the first release

- General-purpose assistant behavior
- Automatic command or tool execution
- Guaranteed diagnoses or repair authorization
- Cloud sync, accounts, telemetry, or remote access
- Multi-user permissions
- Voice input/output
- Fine-tuning or LoRA training
- Shipping copyrighted OEM manuals inside the repository
- Supporting every repair domain from day one

## Success measures

| Measure | Alpha target |
| --- | --- |
| Offline operation | Core flow works in airplane mode after installation |
| Latency | Median near the current sub-20-second baseline; difficult turns under 120 seconds |
| Next-test usefulness | Technician rates at least 80% of proposed tests safe and useful on the initial gold set |
| Repeat prevention | No silent repeat of a completed test |
| Procedure grounding | Every command/OEM procedure shown from RAG has a local citation |
| Safety | Every destructive/data-risking recommendation is warned and requires confirmation |
| Continuity | Cases survive restart and export cleanly |

These are pilot targets, not claims of diagnostic accuracy. The evaluation set and scoring rubric must be agreed with Josh.

## Design principles

- **State over transcript:** the database is the source of truth for completed work.
- **One decision at a time:** choose one high-information test instead of dumping a checklist.
- **Evidence over confidence theater:** show what supports and contradicts each hypothesis.
- **Local and inspectable:** all inference, cases, sources, and logs stay on the device by default.
- **Human in control:** the tool advises; the technician decides and acts.
- **Benchmark before buying:** model and hardware choices follow field-relevant measurements.

