---
id: RB-CEL-005
title: GPS synchronisation loss
faultType: cell_outage
tags: [GPS, sync, timing, PTP]
---

# GPS synchronisation loss

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Loss of GPS/PTP timing reference; cells enter holdover then go off-air for TDD.

## Diagnosis

Check the GPS antenna and PTP grandmaster status.

## Remediation

Fix the GPS antenna cable or fail over to PTP; keep cells in holdover meanwhile.

## Escalation

If not resolved within the SLA, escalate to the tier-2 cell outage team and attach alarm IDs and KPI charts.
