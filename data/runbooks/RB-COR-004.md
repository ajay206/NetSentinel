---
id: RB-COR-004
title: UPF user plane packet drops
faultType: core_packet_loss
tags: [UPF, user plane, GTP]
---

# UPF user plane packet drops

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

User plane function drops GTP-U packets; data sessions stall.

## Diagnosis

Check UPF CPU, session counts and drop counters.

## Remediation

Scale out the UPF; move sessions to a healthy instance.

## Escalation

If not resolved within the SLA, escalate to the tier-2 core packet loss team and attach alarm IDs and KPI charts.
