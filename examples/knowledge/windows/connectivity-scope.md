---
id: internal.windows.connectivity-scope.v1
title: Scope a Windows connectivity complaint before changing configuration
topics:
  - windows
  - wifi
  - ethernet
  - connectivity
  - dns
risk: safe
source_title: Internal synthetic diagnostic fixture
source_version: "1"
verified_at: 2026-08-31
review_after: 2027-02-28
trust_tier: 4
redistribution: synthetic-example
platforms:
  - Windows 10
  - Windows 11
vendors: []
requires_elevation: false
prerequisites: []
side_effects: []
rollback: Not applicable; this card is observational.
---

# Goal

Determine whether the reported failure affects one application, one destination, the local network, or all connectivity before resetting adapters or changing configuration.

# Procedure

1. Record whether the problem occurs on Wi-Fi, Ethernet, or both.
2. Record whether another device on the same network has the same symptom.
3. Check whether the affected computer can reach its configured default gateway.
4. Separately test name resolution and direct IP connectivity.
5. Record the exact error and whether the symptom is intermittent.

# Expected branches

- Another device fails in the same way: prioritize shared router, upstream, or service causes.
- The gateway is unreachable from only one computer: prioritize the local link, adapter, address, and driver path.
- Direct IP works but names fail: prioritize DNS configuration or resolver availability.
- Only one application fails: prioritize application, proxy, firewall, or endpoint-specific causes.

# Safety

Do not reset networking, remove profiles, or change router settings until the failure has been scoped and the current configuration has been recorded.

