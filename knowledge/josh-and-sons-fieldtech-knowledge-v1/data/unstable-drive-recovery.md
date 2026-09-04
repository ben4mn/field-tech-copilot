---
id: joshandsons.data.unstable-drive-recovery.v1
title: "Hard drive spins up, stops, or disappears: stop ordinary access and escalate"
topics:
  - hard drive spins up then stops
  - hard drive disappears
  - disk unknown not initialized
  - unstable SATA hard drive
  - irreplaceable photos
  - professional data recovery
  - GNU ddrescue
  - sector imaging
risk: caution
source_title: GNU ddrescue manual
source_url: https://www.gnu.org/software/ddrescue/manual/ddrescue_manual.html
source_version: "GNU ddrescue 1.30 (2026-01-01)"
verified_at: 2026-09-04
review_after: 2027-03-01
trust_tier: 1
redistribution: paraphrased primary-source recovery guidance
platforms:
  - Windows 11
  - Linux recovery environment
requires_elevation: true
prerequisites:
  - Attempt imaging only when the drive remains continuously detected and the customer accepts the risk.
  - Verify the exact source identity and a healthy, empty destination larger than the source.
side_effects:
  - Any additional read or power cycle can worsen a mechanically failing drive and reduce recoverability.
rollback: Stop imaging, preserve the image and mapfile, and leave the original drive unchanged and powered off.
---

# Hard drive spins up, stops, or disappears

This procedure applies when a mechanical hard drive repeatedly spins down, disappears from Windows, disconnects during simple reads, appears Unknown or Not Initialized, or cannot maintain a stable mounted volume.

## Immediate stop and escalation condition

If customer data is irreplaceable and the drive disappears within seconds, repeatedly spins up and down, clicks, overheats, or cannot remain detected as a block device:

1. Power the drive off.
2. Do not perform more ordinary Windows tests.
3. Explain that further power cycles may reduce the chance of recovery.
4. Recommend a professional data-recovery laboratory.
5. Record that no writes or repair attempts were performed.

This is the required branch for an unstable drive containing irreplaceable photos with no backup.

## Prohibited actions

Never initialize, format, mount read-write, run CHKDSK, repair the filesystem, or use Robocopy, File Explorer, Xcopy, or Copy-Item on the original unstable drive.

Robocopy requires a stable mounted filesystem and is not a failing-drive imaging tool.

## Controlled imaging branch

Consider best-effort sector imaging only when the drive remains continuously detected as a block device and the customer explicitly accepts the risk.

Verify the exact source model, serial number, capacity, and device path. Confirm the destination is healthy, empty, and larger than the source. Keep the source unmounted or read-only.

A first GNU ddrescue pass should use a persistent mapfile and `-n` to avoid the scraping phase or retries:

`sudo ddrescue -n /dev/sdX /mnt/recovery/customer-drive.img /mnt/recovery/customer-drive.map`

Never use `/dev/sdX` until the source identity is verified. Never reverse the source and destination. Stop and escalate if the drive disconnects, clicks, overheats, or cannot remain detected.

Perform filesystem repair and file extraction only against the completed image or a duplicate, never the original drive.
