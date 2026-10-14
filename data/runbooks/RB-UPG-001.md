---
id: RB-UPG-001
title: KPI degradation after software upgrade
faultType: bad_upgrade
tags: [upgrade, software, rollback]
---

# KPI degradation after software upgrade

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

KPIs degrade right after a software upgrade window across upgraded nodes only.

## Diagnosis

Compare upgraded and non-upgraded nodes; check release notes for known issues.

## Remediation

Roll back to the previous software package; open a vendor case with logs.

## Escalation

If not resolved within the SLA, escalate to the tier-2 bad upgrade team and attach alarm IDs and KPI charts.
