---
id: RB-UPG-006
title: Orchestrator rollout partial failure
faultType: bad_upgrade
tags: [orchestrator, CNF, rollout]
---

# Orchestrator rollout partial failure

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Cloud-native function rollout stuck halfway; some pods on new version crash-looping.

## Diagnosis

Check rollout status and pod logs.

## Remediation

Pause and roll back the rollout; fix the image before resuming.

## Escalation

If not resolved within the SLA, escalate to the tier-2 bad upgrade team and attach alarm IDs and KPI charts.
