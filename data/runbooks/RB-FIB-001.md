---
id: RB-FIB-001
title: Fibre cut on aggregation ring
faultType: fibre_cut
tags: [LOS, ring, transport]
---

# Fibre cut on aggregation ring

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Loss of signal (LOS) on both directions of an aggregation ring span; many downstream sites raise communication alarms at once; ring protection switch event.

## Diagnosis

Check optical receive power on both ring nodes; confirm the protection switch; use OTDR to measure distance to the break.

## Remediation

Confirm traffic is on the protection path; dispatch the field fibre splicing team with the OTDR distance; after splicing, revert the ring and verify BER.

## Escalation

If not resolved within the SLA, escalate to the tier-2 fibre cut team and attach alarm IDs and KPI charts.
