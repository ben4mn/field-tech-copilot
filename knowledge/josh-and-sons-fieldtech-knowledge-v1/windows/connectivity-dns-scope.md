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
source_title: Microsoft nslookup command documentation
source_url: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/nslookup
source_version: "accessed 2026-09-02"
verified_at: 2026-09-02
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

1. Record the active adapter and whether other devices share the symptom.
2. Run `ipconfig /all` once and record the address, gateway, DHCP status, and DNS servers.
3. If direct IP reachability is not already established, test the gateway and a known internet IP. Do not repeat successful tests unless network state changes.
4. Run `nslookup <affected-name>` and record the DNS server and exact response.
5. If the default server times out while direct IP works, query the same name against an approved alternate resolver: `nslookup <affected-name> 1.1.1.1`.
6. If the alternate query succeeds, do not retest the unchanged default resolver. Advance to a controlled repair or investigate that resolver's path.
7. Testing another public domain against the same failed resolver is not an alternate-resolver test.
8. Compare applications only when name resolution succeeds but an application still fails.

These observational commands do not require an administrator Command Prompt.

# Expected branches

- Gateway unreachable only on this computer: prioritize link, adapter, addressing, or driver.
- Direct IP succeeds but default lookup fails: prioritize DNS configuration or resolver availability.
- Default resolver fails and explicit alternate succeeds: the configured resolver or its path is the likely fault. The network adapter is not the leading hypothesis.
- Both resolvers fail while direct IP works: investigate local filtering, DNS interception, endpoint security, or DNS-port reachability.
- Name resolution succeeds but one application fails: prioritize application, proxy, firewall, or certificate causes.

# Safety

Do not reset networking, remove profiles, change DNS servers, or alter the router until the original configuration and test results are recorded.