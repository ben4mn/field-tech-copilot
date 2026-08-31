# Conversation analysis

## Product intent

A field technician needs a copilot that remains useful with no internet connection. The core job is not open-ended chat: it is to turn a customer complaint and a stream of test results into a persistent, evidence-based diagnostic process.

The desired behavior is:

1. Understand a natural-language complaint.
2. Maintain facts, open questions, and ranked hypotheses.
3. Select the highest-value next test.
4. Record the result and eliminate contradicted hypotheses.
5. Avoid repeating completed work.
6. Recognize when the evidence supports an intervention or when it remains insufficient.

The external knowledge layer should contain verified commands, safe procedures, manufacturer documentation, and known tests. That material should remain separable from model weights so it can be cited, inspected, and updated.

## Primary user and environment

The initial user is a busy Windows-heavy repair technician working in a low-connectivity region. The tool must be quick to start, simple to maintain, and usable on a mobile laptop. A customer may be watching, so the interface should look like a purpose-built workbench rather than a generic chat site.

Known baseline hardware is a Core Ultra 5 laptop with 32 GB RAM running Qwen3 8B. Typical responses are reportedly under 20 seconds. Up to 60–120 seconds is acceptable for the first few difficult decisions if accuracy improves. Other laptop specifications were shared as images but are not present in the supplied text, so a responsible hardware recommendation is not possible yet.

## Repair domains mentioned

- Networking, Wi-Fi, Ethernet, routers, DNS, and connectivity
- Windows setup, reinstall, reset, recovery, updates, and activation
- Customer data transfer, backup, and basic recovery
- Printers, scanners, drivers, queues, and network printing
- No-boot, no-power, shutdown, charging, and battery faults
- Slow systems, malware, popups, and startup issues
- SSD/RAM upgrades, cloning, and compatibility
- Display, HDMI, USB, cables, ports, and peripherals
- Email, accounts, software setup, and small-business edge cases

## Requirements inferred from the workflow

- Cases must save automatically and resume after restart.
- The diagnostic record must be structured data, not model memory alone.
- Every test and result needs a chronological audit trail.
- Observations, hypotheses, recommendations, and confirmed findings must remain distinct.
- Commands and manufacturer procedures need local citations and version metadata.
- Destructive or irreversible work needs a warning and explicit confirmation.
- The model must be allowed to say that evidence is insufficient.
- The first release should recommend actions but never execute them.
- Knowledge bundles need an offline import and update path.
- A completed case should export to a technician-readable summary.

## Unknowns to resolve during discovery

1. Exact specifications, upgrade paths, ports, and operating systems for all candidate laptops.
2. Whether “talk to it” means typed conversation initially or requires offline speech.
3. Whether deployment should be native Windows, WSL, or Linux.
4. The current prototype, prompts, model quantization, and gold-example format.
5. The first three repair categories the pilot technician wants to evaluate.
6. Retention, encryption, deletion, and backup expectations for case data.
7. Whether this remains an internal tool or may become a product for other technicians.
8. Which vendor materials may legally be redistributed in a knowledge bundle.

## Product risks

| Risk | MVP response |
| --- | --- |
| Hallucinated or unsafe procedure | Retrieve curated cards, cite sources, validate risk metadata, require confirmation |
| Confident diagnosis with weak evidence | Show evidence for/against and permit “insufficient evidence” |
| Repeated or lost work | Store cases and completed-test keys deterministically in SQLite |
| Stale or irrelevant retrieval | Version sources, record verification dates, and test retrieval separately |
| Customer privacy exposure | Local-only defaults, no telemetry, ignored runtime data, anonymized fixtures |
| Premature fine-tuning | Establish prompt/RAG baseline and gold evaluation first |
| Hardware overspending | Benchmark candidate models on each actual laptop before purchasing upgrades |
| Scope sprawl | Pilot networking, Windows boot/update/performance, and printers first |

## Product conclusion

The right first product is a diagnostic case notebook with a replaceable local reasoning engine. Fine-tuning, voice, automatic command execution, broad vendor coverage, and multi-technician features are later decisions. Reliability comes first from explicit state, curated evidence, guardrails, and evaluation—not from a larger prompt or a larger model alone.
