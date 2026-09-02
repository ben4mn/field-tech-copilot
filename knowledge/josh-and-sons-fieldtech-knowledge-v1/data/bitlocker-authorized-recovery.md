---
id: joshandsons.data.bitlocker-authorized-recovery.v1
title: "BitLocker volume locked and recovery key unavailable: pause and obtain authorization"
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
verified_at: 2026-09-02
review_after: 2027-03-01
trust_tier: 1
redistribution: paraphrased Microsoft recovery guidance
platforms:
  - Windows 11
requires_elevation: false
rollback: Relock the volume or safely disconnect it; do not alter protectors, enable automatic unlocking, or decrypt the original drive.
---

# BitLocker volume locked without a recovery key

Use this procedure when a stable drive is detected normally but its Windows volume is locked by BitLocker and the customer has not supplied the recovery key.

The encryption key is the access requirement. Additional SMART, Get-Disk, reliability, filesystem, or file-copy tests do not provide access and should not delay authorization.

## Required next step

1. Pause the data transfer.
2. Do not ask the customer for their Microsoft-account password.
3. Have the customer sign in privately on a trusted device.
4. For a personal Microsoft account, direct the customer to:

   `https://aka.ms/myrecoverykey`

5. For a work or school account, direct the customer to:

   `https://aka.ms/aadrecoverykey`

   The customer may instead need their organization’s IT administrator.

6. Match the displayed recovery-key ID to the locked volume.
7. Have the customer provide only the matching 48-digit recovery key through an approved method.
8. Do not store the key in ordinary case notes, screenshots, email, or chat logs.

## If the key is unavailable

Stop. Securely store or return the original drive. Do not bypass encryption, crack credentials, reset protectors, initialize, format, repair, or decrypt the drive.

## After authorized key access

After the customer supplies the matching key and explicitly authorizes access, unlock the volume through the Windows BitLocker interface. Copy only the approved folders to a verified destination.

Keep the original unchanged. When finished, relock or safely disconnect the volume. Do not enable automatic unlocking or remove BitLocker protection.
