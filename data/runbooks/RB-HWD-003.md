---
id: RB-HWD-003
title: Memory leak causes slow degradation
faultType: hw_drift
tags: [memory, leak, process]
---

# Memory leak causes slow degradation

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Gradual memory growth on a node over weeks; occasional process restarts.

## Diagnosis

Trend memory usage per process.

## Remediation

Schedule a controlled restart; apply the vendor patch for the leak.

## Escalation

If not resolved within the SLA, escalate to the tier-2 hw drift team and attach alarm IDs and KPI charts.
