---
id: RB-COR-006
title: Microburst drops on data centre switch
faultType: core_packet_loss
tags: [microburst, buffer, switch]
---

# Microburst drops on data centre switch

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Intermittent drops at a DC leaf switch during traffic microbursts.

## Diagnosis

Check buffer drop counters at fine granularity.

## Remediation

Tune buffer profiles; spread traffic across more uplinks.

## Escalation

If not resolved within the SLA, escalate to the tier-2 core packet loss team and attach alarm IDs and KPI charts.
