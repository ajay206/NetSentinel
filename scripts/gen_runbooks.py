#!/usr/bin/env python3
# ruff: noqa: E501  (long prose strings in the corpus table)
"""Generate the synthetic runbook corpus (data/runbooks) and the retrieval eval set
(data/eval/qa.jsonl). Deterministic; synthetic only - no vendor or customer content.

Usage: python3 scripts/gen_runbooks.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# fault type -> (code, [(title, tags, symptoms, diagnosis, remediation)])
CORPUS: dict[str, tuple[str, list[tuple[str, list[str], str, str, str]]]] = {
    "fibre_cut": (
        "FIB",
        [
            (
                "Fibre cut on aggregation ring",
                ["LOS", "ring", "transport"],
                "Loss of signal (LOS) on both directions of an aggregation ring span; many downstream "
                "sites raise communication alarms at once; ring protection switch event.",
                "Check optical receive power on both ring nodes; confirm the protection switch; use "
                "OTDR to measure distance to the break.",
                "Confirm traffic is on the protection path; dispatch the field fibre splicing team "
                "with the OTDR distance; after splicing, revert the ring and verify BER.",
            ),
            (
                "Last-mile access fibre break",
                ["LOS", "access", "single-site"],
                "Single access site down with LOS on its uplink port; the parent hub is healthy; "
                "no ring alarm.",
                "Verify the hub port shows LOS and no light; check recent civil works near the route.",
                "Raise a field ticket for the access fibre; enable microwave backup if present; "
                "notify the region of the expected outage.",
            ),
            (
                "DWDM channel loss of signal",
                ["OTN", "DWDM", "amplifier", "OLP"],
                "OTN/DWDM channel LOS and OLP low-power alarms on an optical line amplifier; "
                "multiple wavelengths affected at the same time.",
                "Compare per-channel power across amplifier stages; check the OSC channel; separate "
                "an amplifier fault from a line fibre cut.",
                "If the line is cut, reroute wavelengths over the alternate path; if the amplifier "
                "failed, swap the card per spares procedure.",
            ),
            (
                "Microwave backup failover after fibre cut",
                ["microwave", "failover", "capacity"],
                "Primary fibre LOS followed by traffic moving to the microwave backup link; "
                "throughput capped and congestion on the backup hop.",
                "Confirm the microwave link is carrying traffic; check adaptive modulation level "
                "and fade margin.",
                "Apply QoS to prioritise voice and signalling while on backup; track fibre repair; "
                "switch back when the fibre is restored.",
            ),
            (
                "CPRI fronthaul fibre fault",
                ["CPRI", "fronthaul", "radio unit"],
                "Radio unit unreachable: CPRI link down between baseband and remote radio head; "
                "one sector off-air.",
                "Check SFP diagnostics (Rx power, temperature) at both ends; swap patch cords.",
                "Replace the faulty SFP or jumper; re-enable the sector and confirm VSWR and RSSI.",
            ),
            (
                "Patch panel fibre disconnection",
                ["patch panel", "ODF", "human error"],
                "Abrupt LOS right after on-site work in an exchange; ODF patch moved or disconnected.",
                "Correlate the alarm time with site access logs and change tickets.",
                "Ask the on-site engineer to reseat the patch on the ODF; update port documentation.",
            ),
        ],
    ),
    "power_failure": (
        "PWR",
        [
            (
                "Mains power failure with battery discharge",
                ["mains", "battery", "rectifier"],
                "Mains failure alarm, rectifier on battery, battery voltage dropping; site still up.",
                "Estimate battery autonomy from voltage and load; check utility outage maps.",
                "Dispatch a mobile generator before battery low-voltage disconnect; shed non-critical "
                "load.",
            ),
            (
                "Generator failed to start",
                ["generator", "genset", "fuel"],
                "Mains failure and generator fail-to-start alarm; batteries draining.",
                "Check genset controller alarms, fuel level and starter battery.",
                "Send a technician to manually start or refuel the generator; escalate if autonomy "
                "is under one hour.",
            ),
            (
                "Rectifier module failure",
                ["rectifier", "DC", "redundancy"],
                "Rectifier module fail alarm, reduced DC capacity, mains present.",
                "Check N+1 redundancy and remaining rectifier load share.",
                "Hot-swap the failed rectifier module; verify load sharing.",
            ),
            (
                "Battery low-voltage disconnect site down",
                ["LVD", "battery", "site down"],
                "Whole site went dark after a long mains outage; LVD triggered; all node alarms "
                "then silence.",
                "Confirm last battery voltage reading before loss of management.",
                "Restore power with generator; check batteries for deep-discharge damage; bring "
                "nodes up in order: transport first, then radio.",
            ),
            (
                "High temperature after cooling failure",
                ["HVAC", "temperature", "cooling"],
                "Air conditioning failure and high shelter temperature; equipment thermal alarms.",
                "Check HVAC alarms and outdoor temperature; identify hot equipment.",
                "Dispatch HVAC maintenance; temporarily power down non-essential equipment.",
            ),
            (
                "Power supply unit failure in router",
                ["PSU", "router", "redundant"],
                "Router PSU failure alarm; redundant PSU carrying the load.",
                "Verify the second PSU is healthy and the input feed is present.",
                "Replace the PSU under the hardware RMA process during a maintenance window.",
            ),
        ],
    ),
    "cell_outage": (
        "CEL",
        [
            (
                "Cell out of service after radio fault",
                ["cell down", "radio", "sector"],
                "A cell is out of service; RRC setup attempts fall to zero for that cell; "
                "neighbour cells absorb traffic.",
                "Check radio unit alarms and baseband status for that cell.",
                "Lock and unlock the cell; if it stays down, reset the radio unit and raise a "
                "hardware ticket.",
            ),
            (
                "Sleeping cell with no alarms",
                ["sleeping cell", "zero traffic", "KPI"],
                "Cell reports no alarms but carries zero traffic; availability looks fine while "
                "throughput is flat at zero.",
                "Compare traffic KPIs with neighbours; look for stuck counters.",
                "Restart the cell; open a vendor case if it recurs.",
            ),
            (
                "VSWR alarm on antenna path",
                ["VSWR", "antenna", "feeder"],
                "High VSWR alarm on a sector; reduced coverage and drop call rate rising.",
                "Run a VSWR/DTF test to locate the antenna or feeder fault.",
                "Send a rigger to fix the connector or replace the feeder jumper.",
            ),
            (
                "gNB baseband unit restart loop",
                ["gNB", "baseband", "reboot"],
                "gNB baseband keeps restarting; all cells of the site flap.",
                "Collect crash logs; check for recent software or configuration changes.",
                "Roll back the last change; if the loop continues, replace the baseband board.",
            ),
            (
                "GPS synchronisation loss",
                ["GPS", "sync", "timing", "PTP"],
                "Loss of GPS/PTP timing reference; cells enter holdover then go off-air for TDD.",
                "Check the GPS antenna and PTP grandmaster status.",
                "Fix the GPS antenna cable or fail over to PTP; keep cells in holdover meanwhile.",
            ),
            (
                "License expiry takes cells off-air",
                ["license", "capacity", "software"],
                "Cells locked after a capacity license expired; license alarm on the node.",
                "Check license status and expiry date on the node.",
                "Install the renewed license key and unlock the cells.",
            ),
        ],
    ),
    "congestion": (
        "CON",
        [
            (
                "Cell congestion high PRB utilisation",
                ["PRB", "congestion", "busy hour"],
                "PRB utilisation above 90% during busy hour; throughput per user drops; no fault "
                "alarms.",
                "Check traffic growth trend and neighbour load.",
                "Enable load balancing to neighbours; plan a capacity add (carrier or sector).",
            ),
            (
                "Backhaul link saturation",
                ["backhaul", "utilisation", "transport"],
                "Backhaul interface utilisation near 100%; packet drops on the site uplink.",
                "Check interface counters and queue drops on the hub router.",
                "Upgrade the backhaul capacity; apply QoS shaping in the meantime.",
            ),
            (
                "Event crowd capacity surge",
                ["event", "stadium", "surge"],
                "Sudden traffic surge around a venue during an event; RRC setup failures due to "
                "admission control.",
                "Correlate with the events calendar; check admission rejections.",
                "Activate temporary capacity (cell on wheels); adjust admission thresholds.",
            ),
            (
                "Signalling storm on core",
                ["signalling", "storm", "AMF"],
                "Burst of attach/registration requests overloading the AMF/MME after an outage "
                "recovery.",
                "Check registration rate and overload control status.",
                "Enable overload protection and backoff timers; stagger site recovery.",
            ),
            (
                "DNS resolver overload",
                ["DNS", "latency", "core"],
                "High DNS query latency and timeouts; browsing slow while radio KPIs look normal.",
                "Check resolver CPU and query rate; look for abusive clients.",
                "Scale out resolvers; rate-limit abusive sources.",
            ),
            (
                "Uplink interference raises noise floor",
                ["interference", "uplink", "RSSI"],
                "High uplink RSSI noise floor; uplink throughput and accessibility degrade.",
                "Inspect uplink interference per PRB; check for external interferers.",
                "Report to spectrum team; apply interference rejection settings.",
            ),
        ],
    ),
    "bad_upgrade": (
        "UPG",
        [
            (
                "KPI degradation after software upgrade",
                ["upgrade", "software", "rollback"],
                "KPIs degrade right after a software upgrade window across upgraded nodes only.",
                "Compare upgraded and non-upgraded nodes; check release notes for known issues.",
                "Roll back to the previous software package; open a vendor case with logs.",
            ),
            (
                "Configuration push error",
                ["config", "change", "misconfiguration"],
                "Alarms start right after a bulk configuration push; wrong parameter values.",
                "Diff the running configuration against the golden template.",
                "Revert the configuration change set; fix the template before re-pushing.",
            ),
            (
                "Failed firmware upgrade bricks card",
                ["firmware", "card", "boot"],
                "Line card stuck in boot after firmware upgrade; ports down.",
                "Check the card boot log and firmware version.",
                "Reload the card from the backup firmware bank; RMA if it still fails.",
            ),
            (
                "Certificate expiry breaks interfaces",
                ["certificate", "TLS", "IPsec"],
                "IPsec/TLS tunnels fail after a certificate expired; management and S1/NG links down.",
                "Check certificate validity dates on nodes and the security gateway.",
                "Renew and install certificates; enable expiry monitoring.",
            ),
            (
                "Parameter change causes handover failures",
                ["handover", "neighbour", "parameter"],
                "Handover success rate drops after neighbour list or parameter change.",
                "Review the recent parameter change log for the cluster.",
                "Restore previous handover parameters and neighbour relations.",
            ),
            (
                "Orchestrator rollout partial failure",
                ["orchestrator", "CNF", "rollout"],
                "Cloud-native function rollout stuck halfway; some pods on new version crash-looping.",
                "Check rollout status and pod logs.",
                "Pause and roll back the rollout; fix the image before resuming.",
            ),
        ],
    ),
    "hw_drift": (
        "HWD",
        [
            (
                "Optical transceiver degradation",
                ["SFP", "optical power", "degradation"],
                "Slowly falling optical Rx power and rising pre-FEC BER over days; no outage yet.",
                "Trend transceiver DDM values; compare with thresholds.",
                "Replace the transceiver in the next maintenance window before it fails.",
            ),
            (
                "Fan failure and rising temperature",
                ["fan", "temperature", "chassis"],
                "Fan tray failure alarm; chassis temperature creeping up.",
                "Check fan speed readings and inlet temperature.",
                "Replace the fan tray; check air filters.",
            ),
            (
                "Memory leak causes slow degradation",
                ["memory", "leak", "process"],
                "Gradual memory growth on a node over weeks; occasional process restarts.",
                "Trend memory usage per process.",
                "Schedule a controlled restart; apply the vendor patch for the leak.",
            ),
            (
                "Clock oscillator drift",
                ["oscillator", "holdover", "frequency"],
                "Frequency offset slowly increasing in holdover; sync quality alarms.",
                "Measure frequency offset against the reference.",
                "Replace the oscillator or timing card.",
            ),
            (
                "Disk wear on server",
                ["disk", "SMART", "server"],
                "SMART warnings and increasing I/O latency on a compute node.",
                "Check SMART attributes and RAID state.",
                "Replace the disk and rebuild the RAID.",
            ),
            (
                "Radio unit power amplifier degradation",
                ["PA", "output power", "radio unit"],
                "Radio unit output power slowly dropping; coverage shrinking at cell edge.",
                "Trend transmit power and PA temperature.",
                "Replace the radio unit under RMA.",
            ),
        ],
    ),
    "core_packet_loss": (
        "COR",
        [
            (
                "Packet loss on core router link",
                ["packet loss", "core", "CRC"],
                "Packet loss and CRC errors on a core router link; many sites see degraded "
                "throughput and latency.",
                "Check interface errors, optics and the link partner.",
                "Shift traffic away with IGP metrics; replace optics or cable.",
            ),
            (
                "BGP session flap",
                ["BGP", "routing", "flap"],
                "BGP session flapping with a peer; route withdrawals and traffic black-holing.",
                "Check BGP logs, hold timers and the underlying link.",
                "Dampen the session; fix the underlying link or configuration.",
            ),
            (
                "MPLS LSP down",
                ["MPLS", "LSP", "RSVP"],
                "MPLS LSP down; services over the tunnel reroute or fail.",
                "Check RSVP/LDP state and the path.",
                "Resignal the LSP; fix the failed link.",
            ),
            (
                "UPF user plane packet drops",
                ["UPF", "user plane", "GTP"],
                "User plane function drops GTP-U packets; data sessions stall.",
                "Check UPF CPU, session counts and drop counters.",
                "Scale out the UPF; move sessions to a healthy instance.",
            ),
            (
                "Firewall session table full",
                ["firewall", "NAT", "sessions"],
                "Core firewall/NAT session table full; new connections dropped.",
                "Check session table utilisation and top talkers.",
                "Increase limits or shorten timeouts; block abusive sources.",
            ),
            (
                "Microburst drops on data centre switch",
                ["microburst", "buffer", "switch"],
                "Intermittent drops at a DC leaf switch during traffic microbursts.",
                "Check buffer drop counters at fine granularity.",
                "Tune buffer profiles; spread traffic across more uplinks.",
            ),
        ],
    ),
}

# Eval queries: paraphrases (not titles) -> expected runbook (fault, index)
QA: list[tuple[str, str, int]] = [
    ("many sites lost signal on the ring, protection switched", "fibre_cut", 0),
    ("OTDR shows a break on the aggregation ring span", "fibre_cut", 0),
    ("one access site has no light on its uplink, hub fine", "fibre_cut", 1),
    ("optical amplifier low power several wavelengths gone", "fibre_cut", 2),
    ("traffic moved to microwave after the fibre went down", "fibre_cut", 3),
    ("remote radio head unreachable CPRI link down", "fibre_cut", 4),
    ("LOS right after engineer worked on the ODF", "fibre_cut", 5),
    ("site running on batteries, utility outage", "power_failure", 0),
    ("genset won't start during mains outage", "power_failure", 1),
    ("one rectifier module failed, mains ok", "power_failure", 2),
    ("site completely dark after LVD tripped", "power_failure", 3),
    ("shelter overheating, air con broken", "power_failure", 4),
    ("router power supply unit alarm, redundant one carrying load", "power_failure", 5),
    ("cell off air with radio unit alarm", "cell_outage", 0),
    ("cell shows zero traffic but no alarms at all", "cell_outage", 1),
    ("high VSWR on sector, drops increasing", "cell_outage", 2),
    ("baseband keeps rebooting, cells flapping", "cell_outage", 3),
    ("lost GPS timing, TDD cells in holdover", "cell_outage", 4),
    ("cells locked because the license expired", "cell_outage", 5),
    ("PRB usage over 90 percent in busy hour", "congestion", 0),
    ("site uplink saturated, queue drops on hub router", "congestion", 1),
    ("stadium concert causing admission rejections", "congestion", 2),
    ("AMF overloaded by registration burst after recovery", "congestion", 3),
    ("browsing slow, DNS timeouts, radio fine", "congestion", 4),
    ("uplink noise floor high, external interferer", "congestion", 5),
    ("KPIs got worse only on nodes we just upgraded", "bad_upgrade", 0),
    ("alarms after bulk config push, wrong parameters", "bad_upgrade", 1),
    ("line card stuck booting after firmware update", "bad_upgrade", 2),
    ("IPsec tunnels failing, certificate expired", "bad_upgrade", 3),
    ("handover success dropped after neighbour list change", "bad_upgrade", 4),
    ("CNF rollout pods crash looping", "bad_upgrade", 5),
    ("SFP rx power slowly falling, pre-FEC BER rising", "hw_drift", 0),
    ("fan tray failed and chassis getting hot", "hw_drift", 1),
    ("process memory growing for weeks", "hw_drift", 2),
    ("frequency offset drifting in holdover", "hw_drift", 3),
    ("SMART warnings on compute node disk", "hw_drift", 4),
    ("radio transmit power slowly decreasing, cell edge shrinking", "hw_drift", 5),
    ("CRC errors and loss on a core router interface", "core_packet_loss", 0),
    ("BGP peer keeps flapping, routes withdrawn", "core_packet_loss", 1),
    ("RSVP tunnel down, LSP not signalled", "core_packet_loss", 2),
    ("GTP-U drops in user plane, sessions stall", "core_packet_loss", 3),
    ("NAT session table exhausted, new connections fail", "core_packet_loss", 4),
    ("intermittent drops at DC leaf during bursts", "core_packet_loss", 5),
    ("LOS alarm burst across downstream sites", "fibre_cut", 0),
    ("battery voltage dropping, need generator", "power_failure", 0),
    ("sector down after radio hardware fault", "cell_outage", 0),
    ("throughput per user low at peak, no faults", "congestion", 0),
    ("roll back the software release, KPIs degraded", "bad_upgrade", 0),
    ("transceiver degrading, replace before failure", "hw_drift", 0),
    ("packet loss on core link affecting many sites", "core_packet_loss", 0),
]


def rb_id(fault: str, idx: int) -> str:
    return f"RB-{CORPUS[fault][0]}-{idx + 1:03d}"


def render(fault: str, idx: int) -> str:
    title, tags, symptoms, diagnosis, remediation = CORPUS[fault][1][idx]
    return (
        f"---\nid: {rb_id(fault, idx)}\ntitle: {title}\nfaultType: {fault}\n"
        f"tags: [{', '.join(tags)}]\n---\n\n"
        f"# {title}\n\n> Synthetic runbook for the NetSentinel demo. Not vendor guidance.\n\n"
        f"## Symptoms\n\n{symptoms}\n\n## Diagnosis\n\n{diagnosis}\n\n"
        f"## Remediation\n\n{remediation}\n\n"
        "## Escalation\n\nIf not resolved within the SLA, escalate to the tier-2 "
        f"{fault.replace('_', ' ')} team and attach alarm IDs and KPI charts.\n"
    )


def main() -> None:
    rb_dir = ROOT / "data" / "runbooks"
    rb_dir.mkdir(parents=True, exist_ok=True)
    for old in rb_dir.glob("RB-*.md"):
        old.unlink()
    n = 0
    for fault, (_, items) in CORPUS.items():
        for i in range(len(items)):
            (rb_dir / f"{rb_id(fault, i)}.md").write_text(render(fault, i))
            n += 1
    eval_dir = ROOT / "data" / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    with (eval_dir / "qa.jsonl").open("w") as f:
        for q, fault, i in QA:
            f.write(json.dumps({"query": q, "expected": rb_id(fault, i), "faultType": fault}))
            f.write("\n")
    print(f"wrote {n} runbooks and {len(QA)} eval queries")


if __name__ == "__main__":
    main()
