---
id: joshandsons.windows.apipa-dhcp-scope.v1
title: "Windows 169.254 APIPA addressing: scope DHCP before DNS"
topics:
  - Windows 169.254 address
  - APIPA
  - DHCP lease failure
  - Wi-Fi connected without internet
  - missing default gateway
  - ipconfig all
risk: safe
source_title: Microsoft Automatic Private IP Addressing guidance
source_url: https://learn.microsoft.com/en-us/windows-server/troubleshoot/how-to-use-automatic-tcpip-addressing-without-a-dh
verified_at: 2026-09-03
review_after: 2027-03-03
trust_tier: 1
redistribution: paraphrased Microsoft networking guidance
platforms:
  - Windows 11
  - Windows 10
requires_elevation: false
rollback: No changes are made by this read-only diagnostic procedure.
---

# Windows APIPA and DHCP scope

Use this procedure when a Windows computer reports an IPv4 address beginning with
169.254 and the network was not intentionally configured for link-local addressing.

A 169.254 address indicates that Windows did not obtain a usable IPv4 lease from
DHCP. The connection may still display as connected to Wi-Fi, but normal routed
network access generally will not work.

## Safest first diagnostic test

1. Confirm which adapter is being used and record its connection state.
2. Run `ipconfig /all`.
3. Record DHCP Enabled, IPv4 Address, Subnet Mask, Default Gateway, DHCP Server,
   and lease information for the affected adapter.
4. Check whether another device on the same Wi-Fi network receives a normal
   non-169.254 address and working gateway.

## Interpretation

- If only the affected computer has a 169.254 address, prioritize a client-specific
  DHCP, adapter, driver, or saved-network problem.
- If multiple devices cannot obtain valid addresses, prioritize the router,
  access point, DHCP service, or exhausted DHCP scope.
- Do not begin DNS troubleshooting while the affected computer still has unresolved
  APIPA addressing.
- After a valid non-APIPA address and gateway are present, test gateway or direct-IP
  reachability before testing DNS name resolution.

This procedure is read-only and does not authorize changing router, adapter, or
DNS settings.
