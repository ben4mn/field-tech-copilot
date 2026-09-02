# Josh & Sons Field Tech Knowledge — Starter Pack v1

Twelve conservative procedure cards for Field Tech Copilot. The cards prioritize observation, reversible tests, data protection, and clear stop conditions. They are grounded in Microsoft and Dell primary documentation and were packaged on 2026-09-01.

This is decision support, not an autonomous repair manual. Confirm the exact device, preserve customer data, and use manufacturer service documentation before opening hardware or making destructive changes.

## Install on Josh's Dell

1. Extract this ZIP into:

   `C:\Users\joshr\field-tech-copilot\knowledge\josh-and-sons-starter-v1`

2. Open PowerShell and run:

   ```powershell
   cd $env:USERPROFILE\field-tech-copilot
   uv run python -m fieldtech knowledge ingest knowledge\josh-and-sons-starter-v1
   ```

3. Restart Field Tech Copilot. The upper-right badge should show 13 cards total: the original synthetic card plus these 12 cards.

## Included subjects

- Windows connectivity and DNS scoping
- Non-destructive storage health triage
- External USB/SATA drive isolation
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
