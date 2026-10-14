---
id: RB-PWR-003
title: Rectifier module failure
faultType: power_failure
tags: [rectifier, DC, redundancy]
---

# Rectifier module failure

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Rectifier module fail alarm, reduced DC capacity, mains present.

## Diagnosis

Check N+1 redundancy and remaining rectifier load share.

## Remediation

Hot-swap the failed rectifier module; verify load sharing.

## Escalation

If not resolved within the SLA, escalate to the tier-2 power failure team and attach alarm IDs and KPI charts.
