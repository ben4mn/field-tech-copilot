---
id: joshandsons.windows.data-copy-verification.v1
title: Copy customer files to external storage with identity checks and verification
topics:
  - windows
  - backup
  - data-transfer
  - robocopy
  - external-drive
  - documents
  - pictures
  - stable-file-transfer
risk: caution
source_title: Microsoft Robocopy and external storage transfer documentation
source_url: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy
source_version: "accessed 2026-09-01"
verified_at: 2026-09-01
review_after: 2027-03-01
trust_tier: 1
redistribution: paraphrased-primary-source-plus-shop-verification-sequence
platforms:
  - Windows 11
  - Windows 10
vendors:
  - Microsoft
requires_elevation: false
prerequisites:
  - Obtain customer authorization and identify source and destination by label, model, capacity, and drive letter.
  - Confirm sufficient destination free space.
side_effects:
  - Copies customer data to another storage device and may expose private files if the destination is not controlled.
rollback: Delete the authorized destination copy after customer confirmation when retention is no longer required; do not delete the source during transfer.
---

# Goal

Create a verifiable copy without moving, deleting, or silently overwriting the source data.

# Procedure

## Eligibility gate

This procedure applies only when the source volume is stably mounted, normally readable, and remains connected during read-only access.

Do not use this procedure when a drive disappears, disconnects, repeatedly spins down, clicks, reports increasing read errors, appears Not Initialized, or lacks a stable mounted volume. Robocopy is a file-transfer tool, not a failing-drive imaging or recovery tool. Use the unstable-drive recovery procedure instead.

## Copy procedure

1. Record authorized source folders and exclusions; avoid unrelated profiles and application data.
2. Record source and destination identity and free space before copying.
3. For small simple sets, use File Explorer copy. For larger sets, use a logged Robocopy job with conservative retries and without `/MOVE`, `/MIR`, or `/PURGE`.
4. Preserve useful timestamps and create a log. Example pattern: `robocopy "SOURCE" "DESTINATION" /E /Z /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XJ /LOG:"copy-log.txt"`.
5. Review the log, compare expected folder/file totals, and open representative files from the destination.
6. Keep the source unchanged until the customer verifies the delivered copy.

# Expected branches

- Read errors increase or the source disconnects: stop and reassess source health and imaging/recovery options.
- Destination fills or reports errors: stop, preserve the log, and use a verified healthy destination.
- Counts differ because of access errors or junctions: investigate the specific paths; do not assume the copy is complete.

# Safety

Never use synchronization or deletion switches on the first copy. Do not retain customer data longer than authorized. Encrypt and physically control portable destinations when sensitive data is involved.
