---
id: joshandsons.windows.startup-recovery-triage.v1
title: Triage Windows no-boot conditions before reset or reinstall
topics:
  - windows
  - boot
  - startup
  - winre
  - startup-repair
  - bitlocker
  - recovery
risk: caution
source_title: Microsoft Startup Repair and Windows Recovery Environment
source_url: https://support.microsoft.com/en-us/windows/experience/startup-boot/startup-repair
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
requires_elevation: false
prerequisites:
  - Ask whether customer data is backed up.
  - Determine whether BitLocker is enabled and whether the customer controls the recovery key.
  - Record the exact boot error and firmware storage detection.
side_effects:
  - Recovery operations can restart the computer and may request a BitLocker key.
rollback: Exit Windows Recovery Environment without selecting reset, reinstall, format, or partition operations.
---

# Goal

Distinguish firmware or storage detection failure from a Windows startup failure and try the least invasive recovery option first.

# Procedure

1. Record whether the computer powers on, completes POST, detects its system disk in firmware, and reaches Windows Recovery Environment.
2. Disconnect nonessential USB storage and accessories, then retry once.
3. In WinRE, record available options and any BitLocker prompt before proceeding.
4. Select Troubleshoot > Advanced options > Startup Repair only after confirming the target Windows installation.
5. Record Startup Repair's result and exact message.
6. If repair fails, reassess storage health and data-backup needs before System Restore, uninstalling updates, command-line repair, reset, or reinstall.

# Expected branches

- System disk absent in firmware: prioritize storage connection, device failure, firmware settings, or motherboard path.
- Disk detected but WinRE cannot find Windows: prioritize partition, boot configuration, encryption, or filesystem damage.
- Startup Repair succeeds: verify multiple cold boots and Windows health before closing the case.
- Startup Repair fails: preserve the message; do not assume reinstall is the next safe step.

# Safety

Reset, reinstall, partition deletion, formatting, and boot-command changes require separate authorization, verified target identity, data protection, and rollback planning.
