---
id: joshandsons.windows.dism-sfc-repair.v1
title: Repair Windows component and system files with DISM then SFC
topics:
  - windows
  - dism
  - sfc
  - corruption
  - system-files
  - repair
  - windows-update
risk: caution
source_title: Microsoft Use the System File Checker tool to repair system files
source_url: https://support.microsoft.com/en-us/windows/experience/backup-recovery/use-the-system-file-checker-tool-to-repair-missing-or-corrupted-system-files
source_version: "accessed 2026-09-01"
verified_at: 2026-09-01
review_after: 2027-03-01
trust_tier: 1
redistribution: paraphrased-primary-source
platforms:
  - Windows 11
  - Windows 10
vendors:
  - Microsoft
requires_elevation: true
prerequisites:
  - Confirm symptoms support possible Windows component or system-file corruption.
  - Back up irreplaceable data and provide stable power.
  - Record pending updates and allow enough time for completion.
side_effects:
  - Repairs Windows component and protected system files and can take substantial time.
  - A restart may be required.
rollback: Use a preexisting restore point or backup if repair causes a regression; individual replacements do not have a simple per-file undo.
---

# Goal

Use Microsoft's supported order to repair the Windows component store and then protected system files after simpler application-specific causes are excluded.

# Procedure

1. Open an elevated Command Prompt and record the Windows version and current symptom.
2. Run `DISM.exe /Online /Cleanup-Image /RestoreHealth` and wait for completion without interrupting power.
3. Record the final DISM message and error code, if any.
4. Run `sfc /scannow` and wait for verification to reach 100 percent.
5. Record the exact SFC result, restart if required, and repeat the original symptom test.
6. If SFC cannot perform the operation, follow Microsoft's supported safe-mode or recovery guidance rather than repeatedly rerunning commands.

# Expected branches

- DISM and SFC find no corruption: return to application, driver, profile, storage, or hardware hypotheses.
- Corruption is repaired and the symptom resolves: verify restart and repeatability before closing.
- Corruption returns: investigate storage reliability, unstable memory, interrupted updates, malware, and servicing failures.
- DISM cannot obtain repair content: investigate servicing source, policy, network, or Windows Update state.

# Safety

Do not substitute commands copied from unrelated versions of Windows. Do not interrupt DISM or SFC solely because progress pauses. Escalate before reset or reinstall.
