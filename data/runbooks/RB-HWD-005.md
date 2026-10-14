---
id: RB-HWD-005
title: Disk wear on server
faultType: hw_drift
tags: [disk, SMART, server]
---

# Disk wear on server

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

SMART warnings and increasing I/O latency on a compute node.

## Diagnosis

Check SMART attributes and RAID state.

## Remediation

Replace the disk and rebuild the RAID.

## Escalation

If not resolved within the SLA, escalate to the tier-2 hw drift team and attach alarm IDs and KPI charts.
