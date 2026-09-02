---
id: joshandsons.windows.storage-health-readonly.v1
title: Collect Windows storage identity and reliability evidence without writing to the disk
topics:
  - windows
  - disk
  - hdd
  - ssd
  - nvme
  - smart
  - storage
  - io-error
risk: safe
source_title: Microsoft Storage PowerShell documentation
source_url: https://learn.microsoft.com/en-us/powershell/module/storage/get-storagereliabilitycounter
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
  - Identify the target disk by model, serial number when available, capacity, and connection path.
side_effects: []
rollback: Not applicable; these inventory and reliability queries are read-only.
---

# Goal

Collect identity, health, temperature, wear, and error evidence before any operation that could write to a questionable disk.

# Procedure

1. Record whether the disk appears in firmware, Device Manager, Disk Management, and File Explorer.
2. In PowerShell, run `Get-Disk` and record the target disk number, model, size, partition style, and operational status.
3. Run `Get-PhysicalDisk` and record the target device's health and operational status.
4. When supported, run `Get-PhysicalDisk | Get-StorageReliabilityCounter` and record temperature, read/write errors, wear, and power-on hours.
5. Record abnormal sounds, repeated disconnects, spin-up/spin-down behavior, and I/O errors separately from software status.

# Expected branches

- Reliability data reports errors or the device disconnects under simple reads: treat hardware or connection failure as likely and minimize further access.
- The device is stable through one adapter but not another: prioritize cable, dock, bridge chipset, port, or power delivery.
- The disk is visible but no reliability counters appear: the USB bridge may not pass the data; absence of counters is not proof of health.

# Safety

Do not initialize, format, clean, partition, run repair-mode `chkdsk`, or reset reliability counters during evidence collection. If customer data matters, stop repeated power cycles and decide whether imaging or professional recovery is appropriate.
