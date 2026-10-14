---
id: RB-FIB-003
title: DWDM channel loss of signal
faultType: fibre_cut
tags: [OTN, DWDM, amplifier, OLP]
---

# DWDM channel loss of signal

> Synthetic runbook for the NetSentinel demo. Not vendor guidance.

## Symptoms

OTN/DWDM channel LOS and OLP low-power alarms on an optical line amplifier; multiple wavelengths affected at the same time.

## Diagnosis

Compare per-channel power across amplifier stages; check the OSC channel; separate an amplifier fault from a line fibre cut.

## Remediation

If the line is cut, reroute wavelengths over the alternate path; if the amplifier failed, swap the card per spares procedure.

## Escalation

If not resolved within the SLA, escalate to the tier-2 fibre cut team and attach alarm IDs and KPI charts.
