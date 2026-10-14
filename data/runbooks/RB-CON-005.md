---
id: RB-CON-005
title: DNS resolver overload
faultType: congestion
tags: [DNS, latency, core]
---

# DNS resolver overload

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

High DNS query latency and timeouts; browsing slow while radio KPIs look normal.

## Diagnosis

Check resolver CPU and query rate; look for abusive clients.

## Remediation

Scale out resolvers; rate-limit abusive sources.

## Escalation

If not resolved within the SLA, escalate to the tier-2 congestion team and attach alarm IDs and KPI charts.
