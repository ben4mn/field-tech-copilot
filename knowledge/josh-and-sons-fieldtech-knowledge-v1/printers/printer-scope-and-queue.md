---
id: joshandsons.windows.printer-scope-and-queue.v1
title: Scope Windows printer connection, queue, and application-specific failures
topics:
  - windows
  - printer
  - printing
  - spooler
  - queue
  - word
  - pdf
  - offline
risk: caution
source_title: Microsoft fix printer connection and printing problems
source_url: https://support.microsoft.com/en-us/windows/hardware/printer/fix-printer-connection-and-printing-problems-in-windows
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
  - Record pending print jobs before clearing or restarting anything.
side_effects:
  - Restarting the Print Spooler or clearing the queue can interrupt pending jobs.
rollback: Reopen the affected document and resubmit only the jobs the customer still wants printed.
---

# Goal

Separate printer hardware, connection, Windows queue, driver, and application-specific failures.

# Procedure

1. Record printer model, connection type, displayed error, paper/ink state, and whether the printer can produce its own self-test or status page.
2. For USB, reseat the cable and test another known-good port. For network printing, confirm the printer and computer are on the intended network.
3. Open Settings > Bluetooth & devices > Printers & scanners and verify the intended printer is present and selected.
4. Inspect the queue for paused, offline, or stuck jobs; record them before changing the queue.
5. Print a Windows test page, then compare a simple Notepad document, a PDF, and the reported application.
6. If every application fails and the queue is stuck, power-cycle the printer and restart Windows before reinstalling devices or drivers.

# Expected branches

- Printer self-test fails: prioritize printer hardware, supplies, or printer configuration.
- Windows test page succeeds but one application fails: prioritize that application's document, print settings, add-ins, or user profile.
- Jobs remain in the queue from all applications: prioritize spooler, port, driver, or connection.
- Another computer prints successfully: prioritize the affected Windows installation or profile.

# Safety

Do not remove the printer, delete drivers, or clear a queue until the existing configuration and customer-required jobs are recorded.
