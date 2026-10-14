---
id: RB-FIB-004
title: Microwave backup failover after fibre cut
faultType: fibre_cut
tags: [microwave, failover, capacity]
---

# Microwave backup failover after fibre cut

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Primary fibre LOS followed by traffic moving to the microwave backup link; throughput capped and congestion on the backup hop.

## Diagnosis

Confirm the microwave link is carrying traffic; check adaptive modulation level and fade margin.

## Remediation

Apply QoS to prioritise voice and signalling while on backup; track fibre repair; switch back when the fibre is restored.

## Escalation

If not resolved within the SLA, escalate to the tier-2 fibre cut team and attach alarm IDs and KPI charts.
