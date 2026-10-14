---
id: RB-CEL-002
title: Sleeping cell with no alarms
faultType: cell_outage
tags: [sleeping cell, zero traffic, KPI]
---

# Sleeping cell with no alarms

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Cell reports no alarms but carries zero traffic; availability looks fine while throughput is flat at zero.

## Diagnosis

Compare traffic KPIs with neighbours; look for stuck counters.

## Remediation

Restart the cell; open a vendor case if it recurs.

## Escalation

If not resolved within the SLA, escalate to the tier-2 cell outage team and attach alarm IDs and KPI charts.
