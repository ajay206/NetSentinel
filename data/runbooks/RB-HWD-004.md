---
id: RB-HWD-004
title: Clock oscillator drift
faultType: hw_drift
tags: [oscillator, holdover, frequency]
---

# Clock oscillator drift

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Frequency offset slowly increasing in holdover; sync quality alarms.

## Diagnosis

Measure frequency offset against the reference.

## Remediation

Replace the oscillator or timing card.

## Escalation

If not resolved within the SLA, escalate to the tier-2 hw drift team and attach alarm IDs and KPI charts.
