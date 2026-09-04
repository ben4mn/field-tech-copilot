# Josh & Sons Field Tech Knowledge — Starter Pack v1

Sixteen conservative procedure cards for Field Tech Copilot. The cards prioritize observation, reversible tests, data protection, and clear stop conditions. They are grounded in Microsoft, Dell, and GNU primary documentation and were updated through 2026-09-04.

This is decision support, not an autonomous repair manual. Confirm the exact device, preserve customer data, and use manufacturer service documentation before opening hardware or making destructive changes.

## Install on Josh's Dell

1. Extract this ZIP into:

   `C:\Users\joshr\field-tech-copilot\knowledge\josh-and-sons-fieldtech-knowledge-v1`

2. Open PowerShell and run:

   ```powershell
   cd $env:USERPROFILE\field-tech-copilot
   uv run python -m fieldtech knowledge ingest knowledge\josh-and-sons-fieldtech-knowledge-v1
   ```

3. Restart Field Tech Copilot. The upper-right badge should show 17 cards total: the original synthetic card plus these 16 cards.

## Included subjects

- Windows connectivity and DNS scoping
- APIPA and DHCP-first scoping
- Controlled DNS client repair and rollback
- Non-destructive storage health triage
- External USB/SATA drive isolation
- Unstable-drive stop conditions and image-first recovery
- Authorized BitLocker recovery and privacy controls
- Printer connection, queue, and application scoping
- Windows startup and recovery triage
- Dell no-power / no-POST / no-boot / no-video classification
- Blank screen and external display isolation
- Windows battery health reporting
- Thermal and fan symptom scoping
- Microsoft Defender malware triage
- Data copy and transfer verification
- DISM and SFC system-file repair

## Maintenance

Review the cards by 2027-03-01 or sooner if Microsoft or Dell changes the linked procedures. Do not add customer names, passwords, recovery keys, license keys, or private files to the knowledge folder.
