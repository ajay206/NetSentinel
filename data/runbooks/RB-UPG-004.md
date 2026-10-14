---
id: RB-UPG-004
title: Certificate expiry breaks interfaces
faultType: bad_upgrade
tags: [certificate, TLS, IPsec]
---

# Certificate expiry breaks interfaces

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

IPsec/TLS tunnels fail after a certificate expired; management and S1/NG links down.

## Diagnosis

Check certificate validity dates on nodes and the security gateway.

## Remediation

Renew and install certificates; enable expiry monitoring.

## Escalation

If not resolved within the SLA, escalate to the tier-2 bad upgrade team and attach alarm IDs and KPI charts.
