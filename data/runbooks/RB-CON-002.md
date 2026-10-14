---
id: RB-CON-002
title: Backhaul link saturation
faultType: congestion
tags: [backhaul, utilisation, transport]
---

# Backhaul link saturation

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Backhaul interface utilisation near 100%; packet drops on the site uplink.

## Diagnosis

Check interface counters and queue drops on the hub router.

## Remediation

Upgrade the backhaul capacity; apply QoS shaping in the meantime.

## Escalation

If not resolved within the SLA, escalate to the tier-2 congestion team and attach alarm IDs and KPI charts.
