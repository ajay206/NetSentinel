---
id: RB-COR-003
title: MPLS LSP down
faultType: core_packet_loss
tags: [MPLS, LSP, RSVP]
---

# MPLS LSP down

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

MPLS LSP down; services over the tunnel reroute or fail.

## Diagnosis

Check RSVP/LDP state and the path.

## Remediation

Resignal the LSP; fix the failed link.

## Escalation

If not resolved within the SLA, escalate to the tier-2 core packet loss team and attach alarm IDs and KPI charts.
