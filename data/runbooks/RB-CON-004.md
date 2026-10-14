---
id: RB-CON-004
title: Signalling storm on core
faultType: congestion
tags: [signalling, storm, AMF]
---

# Signalling storm on core

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Burst of attach/registration requests overloading the AMF/MME after an outage recovery.

## Diagnosis

Check registration rate and overload control status.

## Remediation

Enable overload protection and backoff timers; stagger site recovery.

## Escalation

If not resolved within the SLA, escalate to the tier-2 congestion team and attach alarm IDs and KPI charts.
