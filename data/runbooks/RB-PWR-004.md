---
id: RB-PWR-004
title: Battery low-voltage disconnect site down
faultType: power_failure
tags: [LVD, battery, site down]
---

# Battery low-voltage disconnect site down

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Whole site went dark after a long mains outage; LVD triggered; all node alarms then silence.

## Diagnosis

Confirm last battery voltage reading before loss of management.

## Remediation

Restore power with generator; check batteries for deep-discharge damage; bring nodes up in order: transport first, then radio.

## Escalation

If not resolved within the SLA, escalate to the tier-2 power failure team and attach alarm IDs and KPI charts.
