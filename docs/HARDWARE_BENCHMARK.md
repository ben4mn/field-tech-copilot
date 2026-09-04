# Hardware and model benchmark

No hardware purchase should be made from model parameter count or a single tokens-per-second number. Measure the actual diagnostic workflow on each complete laptop configuration.

## Inventory template

| Field | Candidate A | Candidate B | Candidate C |
| --- | --- | --- | --- |
| Make/model | | | |
| OS/build | | | |
| CPU | | | |
| iGPU/NPU | | | |
| Discrete GPU/VRAM | | | |
| RAM installed / maximum | | | |
| Memory channels / free slots | | | |
| SSD free space | | | |
| Thunderbolt/USB4/eGPU support | | | |
| Battery health | | | |
| Weight and charger | | | |
| Runtime/backend/version | | | |

## Controlled model run

Hold these constant for every comparison:

- Application commit and prompt version
- Gold-case set and turn order
- Model artifact checksum and quantization
- Context window, reasoning effort, temperature, and retrieval results
- Power mode, charger state, ambient conditions, and cold/warm-run policy

Record:

| Metric | Why it matters |
| --- | --- |
| Load time | Field startup cost |
| Time to first useful output | Perceived responsiveness |
| Total turn time | Fits the 20/120-second target |
| Prompt/evaluation tokens per second | Helps explain latency |
| Peak RAM and VRAM | Detects spill, swapping, and context limits |
| Battery use and temperature | Determines mobile usefulness |
| Schema-valid turn rate | Basic integration reliability |
| Next-test usefulness and safety | The product outcome |
| Repeat-test and citation errors | Guardrail effectiveness |

## Upgrade decision rule

Buy an upgrade only if it clears an agreed field threshold, such as materially improving next-test quality, moving difficult turns below the 120-second ceiling, or enabling a useful model/context that otherwise cannot run. More RAM can increase capacity but may not increase generation speed. A docked desktop GPU can help throughput while reducing mobility and adding enclosure, power, driver, and interface constraints.

The owned 12 GB RTX 3060 is a benchmark candidate, not an automatic recommendation. Confirm laptop eGPU support and compare end-to-end field value before spending money.

## Current profile decision

The 64 GB dual-channel Latitude 5550 is the intended capacity profile for
Qwen3-30B-A3B Q4_K_M. Qwen3 8B remains the fallback and comparison control.
This does not make the RAM upgrade an automatic recommendation for another
machine: repeat the seven synthetic cases, separate cold and warm runs, record
the exact model/runtime hashes, and add technician ratings before spending.
