---
id: RB-COR-001
title: Packet loss on core router link
faultType: core_packet_loss
tags: [packet loss, core, CRC]
---

# Packet loss on core router link

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Packet loss and CRC errors on a core router link; many sites see degraded throughput and latency.

## Diagnosis

Check interface errors, optics and the link partner.

## Remediation

Shift traffic away with IGP metrics; replace optics or cable.

## Escalation

If not resolved within the SLA, escalate to the tier-2 core packet loss team and attach alarm IDs and KPI charts.
