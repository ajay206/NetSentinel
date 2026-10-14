---
id: RB-CEL-001
title: Cell out of service after radio fault
faultType: cell_outage
tags: [cell down, radio, sector]
---

# Cell out of service after radio fault

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

A cell is out of service; RRC setup attempts fall to zero for that cell; neighbour cells absorb traffic.

## Diagnosis

Check radio unit alarms and baseband status for that cell.

## Remediation

Lock and unlock the cell; if it stays down, reset the radio unit and raise a hardware ticket.

## Escalation

If not resolved within the SLA, escalate to the tier-2 cell outage team and attach alarm IDs and KPI charts.
