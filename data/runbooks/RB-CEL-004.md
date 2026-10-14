---
id: RB-CEL-004
title: gNB baseband unit restart loop
faultType: cell_outage
tags: [gNB, baseband, reboot]
---

# gNB baseband unit restart loop

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

gNB baseband keeps restarting; all cells of the site flap.

## Diagnosis

Collect crash logs; check for recent software or configuration changes.

## Remediation

Roll back the last change; if the loop continues, replace the baseband board.

## Escalation

If not resolved within the SLA, escalate to the tier-2 cell outage team and attach alarm IDs and KPI charts.
