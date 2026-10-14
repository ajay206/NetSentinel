---
id: RB-CON-001
title: Cell congestion high PRB utilisation
faultType: congestion
tags: [PRB, congestion, busy hour]
---

# Cell congestion high PRB utilisation

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

PRB utilisation above 90% during busy hour; throughput per user drops; no fault alarms.

## Diagnosis

Check traffic growth trend and neighbour load.

## Remediation

Enable load balancing to neighbours; plan a capacity add (carrier or sector).

## Escalation

If not resolved within the SLA, escalate to the tier-2 congestion team and attach alarm IDs and KPI charts.
