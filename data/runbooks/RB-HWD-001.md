---
id: RB-HWD-001
title: Optical transceiver degradation
faultType: hw_drift
tags: [SFP, optical power, degradation]
---

# Optical transceiver degradation

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

Slowly falling optical Rx power and rising pre-FEC BER over days; no outage yet.

## Diagnosis

Trend transceiver DDM values; compare with thresholds.

## Remediation

Replace the transceiver in the next maintenance window before it fails.

## Escalation

If not resolved within the SLA, escalate to the tier-2 hw drift team and attach alarm IDs and KPI charts.
