---
id: joshandsons.windows.battery-report.v1
title: Generate and interpret a Windows battery report without changing power settings
topics:
  - windows
  - battery
  - charging
  - shutdown
  - capacity
  - powercfg
  - battery-health
risk: safe
source_title: Microsoft Caring for your battery in Windows
source_url: https://support.microsoft.com/en-us/windows/experience/power-battery/caring-for-your-battery-in-windows
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
  - Connect the correct AC adapter if the battery is critically low.
side_effects:
  - Creates a local HTML report containing device battery history.
rollback: Delete the generated HTML report after documenting the required values if retention is unnecessary.
---

# Goal

Collect battery design capacity, current full-charge capacity, cycle information when available, and recent behavior before recommending replacement.

# Procedure

1. Open Command Prompt as administrator.
2. Run `powercfg /batteryreport` and record the generated report path.
3. Open the report and record installed-battery identity, design capacity, full-charge capacity, recent usage, and cycle count when reported.
4. Compare the report with firmware diagnostics, observed runtime, charge behavior, swelling inspection, and unexpected shutdown history.
5. Record the AC adapter identity and whether charging behavior changes with a known-good correct-wattage adapter.

# Expected branches

- Full-charge capacity is substantially below design capacity and runtime is poor: battery wear is supported.
- Capacity looks plausible but shutdowns occur under load: investigate voltage sag, adapter, firmware, thermals, and system load.
- Battery is absent or not detected: investigate connector, pack electronics, firmware, and board path.
- Swelling is present: stop charging and follow safe battery handling procedures.

# Safety

Do not use one percentage alone as a diagnosis. Do not puncture, compress, heat, or continue charging a swollen or physically damaged lithium battery.
