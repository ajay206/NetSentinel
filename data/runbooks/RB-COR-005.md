---
id: RB-COR-005
title: Firewall session table full
faultType: core_packet_loss
tags: [firewall, NAT, sessions]
---

# Firewall session table full

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Core firewall/NAT session table full; new connections dropped.

## Diagnosis

Check session table utilisation and top talkers.

## Remediation

Increase limits or shorten timeouts; block abusive sources.

## Escalation

If not resolved within the SLA, escalate to the tier-2 core packet loss team and attach alarm IDs and KPI charts.
