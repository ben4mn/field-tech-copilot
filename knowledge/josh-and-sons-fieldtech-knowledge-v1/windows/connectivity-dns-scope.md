---
id: joshandsons.windows.connectivity-dns-scope.v1
title: Scope Windows connectivity and DNS failure before resetting networking
topics:
  - windows
  - wifi
  - ethernet
  - connectivity
  - internet
  - dns
  - ipconfig
  - nslookup
risk: safe
source_title: Microsoft DNS troubleshooting and Windows command documentation
source_url: https://learn.microsoft.com/en-us/windows-server/networking/dns/troubleshoot/troubleshoot-dns-server
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
  - Record whether the issue affects Wi-Fi, Ethernet, or both.
side_effects: []
rollback: Not applicable; this card is observational.
---

# Goal

Locate the failing layer before changing adapters, DNS servers, profiles, or router settings.

# Procedure

1. Record the adapter in use and whether another device on the same network has the symptom.
2. Run `ipconfig /all` and record the adapter address, default gateway, DHCP status, and DNS servers.
3. Ping the configured default gateway.
4. Test direct IP reachability with a known IP address appropriate to the environment.
5. Run `nslookup <affected-name>` and record the responding DNS server, returned address, or exact error.
6. Compare one affected application with another application before calling the failure system-wide.

# Expected branches

- Gateway unreachable on only this computer: prioritize link, adapter, addressing, driver, or local hardware.
- Multiple devices cannot reach the gateway or internet: prioritize shared network equipment or upstream service.
- Direct IP succeeds but name lookup fails: prioritize DNS configuration or resolver availability.
- Name resolution succeeds but one application fails: prioritize application, proxy, firewall, certificate, or endpoint-specific causes.

# Safety

Do not run network reset, remove profiles, change DNS servers, or alter the router until the current configuration and test results are recorded.
