---
id: RB-UPG-003
title: Failed firmware upgrade bricks card
faultType: bad_upgrade
tags: [firmware, card, boot]
---

# Failed firmware upgrade bricks card

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Line card stuck in boot after firmware upgrade; ports down.

## Diagnosis

Check the card boot log and firmware version.

## Remediation

Reload the card from the backup firmware bank; RMA if it still fails.

## Escalation

If not resolved within the SLA, escalate to the tier-2 bad upgrade team and attach alarm IDs and KPI charts.
