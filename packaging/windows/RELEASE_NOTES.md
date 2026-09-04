## Field Kit Lite preview

This Windows x64 installer contains Field Tech Copilot, a pinned llama.cpp CPU
runtime, the official Qwen3-1.7B Q8_0 GGUF, starter synthetic knowledge, the
reviewed 16-card Josh & Sons field pack, and third-party license files. Setup
and the core case workflow do not require an internet connection after the
installer has been downloaded.

Important limitations:

- This is pre-alpha decision-support software for trained technicians.
- The Lite model is included to evaluate the offline workflow; it has not been
  validated for field diagnosis.
- The preview is unsigned unless the release assets show a trusted Authenticode
  publisher. Windows SmartScreen or organization policy may block it.
- No command or repair action is executed automatically.

Safety and workflow updates in this build:

- The reviewed 16-card Josh & Sons field procedure pack is included offline.
- New evidence, refreshes, timeouts, and rejected output immediately invalidate stale actions.
- Duplicate action completion is blocked atomically.
- BitLocker unlock/copy is a confirmed `caution` intervention; recovery keys are never stored.
- Unstable original media is protected while verified images or duplicates can be used as copy sources.
- One bounded, audited guard-repair attempt is allowed; provider failures hard-stop.

Requirements: Windows 10 22H2 or Windows 11, x64 CPU, 8 GB RAM, and 6 GB free
disk space. Verify the adjacent `.sha256` file before installing.
