---
id: RB-COR-002
title: BGP session flap
faultType: core_packet_loss
tags: [BGP, routing, flap]
---

# BGP session flap

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

BGP session flapping with a peer; route withdrawals and traffic black-holing.

## Diagnosis

Check BGP logs, hold timers and the underlying link.

## Remediation

Dampen the session; fix the underlying link or configuration.

## Escalation

If not resolved within the SLA, escalate to the tier-2 core packet loss team and attach alarm IDs and KPI charts.
