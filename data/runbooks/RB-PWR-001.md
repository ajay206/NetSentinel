---
id: RB-PWR-001
title: Mains power failure with battery discharge
faultType: power_failure
tags: [mains, battery, rectifier]
---

# Mains power failure with battery discharge

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Mains failure alarm, rectifier on battery, battery voltage dropping; site still up.

## Diagnosis

Estimate battery autonomy from voltage and load; check utility outage maps.

## Remediation

Dispatch a mobile generator before battery low-voltage disconnect; shed non-critical load.

## Escalation

If not resolved within the SLA, escalate to the tier-2 power failure team and attach alarm IDs and KPI charts.
