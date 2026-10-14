---
id: RB-UPG-002
title: Configuration push error
faultType: bad_upgrade
tags: [config, change, misconfiguration]
---

# Configuration push error

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Alarms start right after a bulk configuration push; wrong parameter values.

## Diagnosis

Diff the running configuration against the golden template.

## Remediation

Revert the configuration change set; fix the template before re-pushing.

## Escalation

If not resolved within the SLA, escalate to the tier-2 bad upgrade team and attach alarm IDs and KPI charts.
