---
id: joshandsons.data.bitlocker-authorized-recovery.v1
title: "Handle a locked BitLocker volume through authorized recovery"
topics:
  - BitLocker locked volume
  - 48-digit recovery key
  - Microsoft account recovery key
  - work or school recovery key
  - encrypted NVMe data transfer
  - customer privacy
risk: caution
source_title: Microsoft Find your BitLocker recovery key
source_url: https://support.microsoft.com/en-us/windows/security/encryption/find-your-bitlocker-recovery-key
verified_at: 2026-09-04
review_after: 2027-03-01
trust_tier: 1
redistribution: paraphrased Microsoft recovery guidance
platforms:
  - Windows 11
requires_elevation: false
prerequisites:
  - Verify customer ownership or authorization and record the approved folder scope without recording the recovery key.
  - Have the customer privately confirm that the displayed recovery-key ID matches their key.
  - Confirm the drive is stable before unlocking or copying data.
side_effects:
  - Unlocking exposes customer data to the authorized Windows session until the volume is relocked or safely disconnected.
rollback: Relock the volume or safely disconnect it; do not alter protectors, enable automatic unlocking, or decrypt the original drive.
---

# Handle a locked BitLocker volume through authorized recovery

Use this procedure when a stable drive is detected normally but its Windows volume is locked by BitLocker.

The encryption key is the access requirement. SMART, Get-Disk, reliability, filesystem, and file-copy tests cannot bypass BitLocker.

## Before proceeding

1. Verify that the customer owns the device or is authorized to access its data.
2. Record the customer's authorization and approved folder scope, but never record the recovery key itself.
3. Match the recovery-key ID shown by Windows to the customer's recovery key.
4. Do not initialize, format, repair, decrypt, or alter BitLocker protectors on the original drive.

## If the authorized recovery key is unavailable

1. Pause the data transfer.
2. Do not request the customer's Microsoft-account password.
3. Have the customer sign in privately on a trusted device.
4. For a personal Microsoft account, direct the customer to:

   `https://aka.ms/myrecoverykey`

5. For a work or school account, direct the customer to:

   `https://aka.ms/aadrecoverykey`

   The customer may instead need their organization's IT administrator.

6. Have the customer compare the displayed key ID and privately enter the matching 48-digit key themselves into the trusted Windows BitLocker recovery prompt.
7. Do not ask the customer to read, paste, send, or otherwise provide the recovery key to the technician.
8. Do not store the key in case notes, screenshots, email, chat logs, prompts, or results.

If the key cannot be obtained, stop and securely store or return the original drive. Do not bypass encryption or attempt credential cracking.

## If the authorized recovery key is available

Unlocking or accessing customer data is a CAUTION action and requires explicit technician confirmation.

1. Have the customer confirm that the key ID matches the locked volume without revealing the recovery key itself.
2. Confirm the customer's approved folders and destination.
3. Unlock the volume through the standard Windows BitLocker interface.
4. Do not enable automatic unlocking, remove BitLocker protection, or decrypt the original drive.
5. Confirm the drive remains stable before copying.
6. Use the separate approved data-copy procedure to copy only the authorized folders to a verified destination.
7. Relock or safely disconnect the volume when finished.

## Stop conditions

Stop and reassess if the key does not match, authorization is unclear, the drive disconnects, read errors increase, or the requested data exceeds the approved scope.
