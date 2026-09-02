---
id: joshandsons.dell.startup-symptom-classification.v1
title: Classify Dell no-power, no-POST, no-boot, and no-video symptoms
topics:
  - dell
  - laptop
  - desktop
  - no-power
  - no-post
  - no-boot
  - no-video
  - diagnostic-led
risk: safe
source_title: Dell Resolve No Power, No POST, No Boot or No Video Issues
source_url: https://www.dell.com/support/kbdoc/en-us/000125609/resolve-no-power-no-post-no-boot-or-no-video-issues-with-your-dell-computer
source_version: "accessed 2026-09-01"
verified_at: 2026-09-01
review_after: 2027-03-01
trust_tier: 2
redistribution: paraphrased-primary-source
platforms: []
vendors:
  - Dell
requires_elevation: false
prerequisites:
  - Record the Dell service tag without including customer identity.
side_effects: []
rollback: Reconnect only the peripherals that were disconnected for isolation.
---

# Goal

Name the startup failure correctly before choosing tests or parts.

# Procedure

1. Observe AC-adapter LED behavior, charge indicator, power-button LED, fans, sounds, keyboard lights, and display backlight.
2. Record all diagnostic LED or beep patterns exactly; do not translate from memory when a model-specific table is available.
3. Classify the symptom:
   - No power: no meaningful signs of electrical activity.
   - No POST: powers on but does not complete hardware self-test.
   - No boot: POST completes but the operating system does not load.
   - No video: system activity is present but no usable image appears.
4. Disconnect nonessential peripherals and external storage, then retry once.
5. Verify the correct known-good power source and rated adapter before opening the system.

# Expected branches

- Adapter LED extinguishes when connected: suspect a short or overload in the system or DC-in path.
- Diagnostic code appears: use the service manual for that exact model and code.
- External display works while the internal display does not: prioritize panel, cable, backlight, hinge path, or display selection.
- POST completes and the disk is detected: move to operating-system or storage boot triage.

# Safety

This card stops before disassembly, internal power-rail testing, RTC reset, firmware update, or part replacement. Use the exact service manual and ESD controls for internal work.
