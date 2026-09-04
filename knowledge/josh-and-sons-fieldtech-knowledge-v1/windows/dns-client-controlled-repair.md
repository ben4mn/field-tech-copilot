---
id: joshandsons.windows.dns-client-controlled-repair.v1
title: Apply and roll back a controlled Windows DNS client override
topics:
  - windows
  - dns
  - name resolution
  - Set-DnsClientServerAddress
risk: caution
source_title: Microsoft Set-DnsClientServerAddress documentation
source_url: https://learn.microsoft.com/en-us/powershell/module/dnsclient/set-dnsclientserveraddress
verified_at: 2026-09-02
requires_elevation: true
prerequisites:
  - Confirm direct IP connectivity works and the configured resolver fails for the same domain.
  - Record the interface alias and existing IPv4 DNS configuration, including whether it came from DHCP.
  - Use only an organization-approved alternate resolver that already succeeded during testing.
rollback: Restore the recorded static DNS addresses, or use ResetServerAddresses if DNS originally came from DHCP.
---

# Controlled Windows DNS client repair

Use only when direct IP connectivity works, the configured DNS resolver fails, and the same domain resolves through an approved alternate DNS server.

Do not repeat completed ping, ipconfig, or nslookup tests.

## Prerequisites

1. Identify the affected interface alias.
2. Record its current IPv4 DNS configuration:

`Get-DnsClientServerAddress -InterfaceAlias "Wi-Fi" -AddressFamily IPv4`

3. Determine whether DNS came from DHCP or was deliberately static.
4. On managed or domain networks, use only organization-approved DNS servers or escalate.

## Caution intervention

1. Obtain explicit technician approval before changing DNS.
2. Use the exact approved resolver that succeeded during testing:

`Set-DnsClientServerAddress -InterfaceAlias "Wi-Fi" -ServerAddresses ("<successful-approved-resolver>")`

Replace the placeholder with the successful resolver IP. Never enter the placeholder literally. Run the command in elevated PowerShell.

## Mandatory rollback

Include the appropriate rollback command in every proposed intervention.

If DNS originally came from DHCP:

`Set-DnsClientServerAddress -InterfaceAlias "Wi-Fi" -ResetServerAddresses`

If DNS was originally static, restore the exact addresses recorded before the change:

`Set-DnsClientServerAddress -InterfaceAlias "Wi-Fi" -ServerAddresses ("<recorded-addresses>")`

Never guess the previous addresses.

## Verification

1. Run `nslookup` for the same domain without specifying a server.
2. Confirm it uses the new configured resolver.
3. Test the affected browser or application.
4. Record the outcome.

Rollback immediately if the symptom remains, internal names fail, or connectivity worsens.
