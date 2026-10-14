---
id: RB-FIB-002
title: Last-mile access fibre break
faultType: fibre_cut
tags: [LOS, access, single-site]
---

# Last-mile access fibre break

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Single access site down with LOS on its uplink port; the parent hub is healthy; no ring alarm.

## Diagnosis

Verify the hub port shows LOS and no light; check recent civil works near the route.

## Remediation

Raise a field ticket for the access fibre; enable microwave backup if present; notify the region of the expected outage.

## Escalation

If not resolved within the SLA, escalate to the tier-2 fibre cut team and attach alarm IDs and KPI charts.
