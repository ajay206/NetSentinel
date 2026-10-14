---
id: RB-FIB-005
title: CPRI fronthaul fibre fault
faultType: fibre_cut
tags: [CPRI, fronthaul, radio unit]
---

# CPRI fronthaul fibre fault

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Radio unit unreachable: CPRI link down between baseband and remote radio head; one sector off-air.

## Diagnosis

Check SFP diagnostics (Rx power, temperature) at both ends; swap patch cords.

## Remediation

Replace the faulty SFP or jumper; re-enable the sector and confirm VSWR and RSSI.

## Escalation

If not resolved within the SLA, escalate to the tier-2 fibre cut team and attach alarm IDs and KPI charts.
