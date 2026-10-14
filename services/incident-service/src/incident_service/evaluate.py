from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from netgen import build_topology
from netgen.alarms import fibre_cut, make_alarm

from incident_service.clustering import compression_ratio, replay

UTC = UTC


def _generate_noise_alarms(
    rng: random.Random,
    count: int,
    sites: list[int],
    start: datetime,
    end: datetime,
) -> list[tuple[float, dict[str, Any]]]:
    noise: list[tuple[float, dict[str, Any]]] = []
    total_seconds = (end - start).total_seconds()
    for i in range(count):
        offset = rng.random() * total_seconds
        site_id = rng.choice(sites)
        alarm_time = start + timedelta(seconds=offset)
        alarm = make_alarm(
            rng,
            alarm_type="equipmentAlarm",
            perceived_severity="warning",
            probable_cause="heatingVentilationCoolingSystemProblem",
            specific_problem="Flapping fan",
            alarmed_object_id=f"noise-{i}",
            site_id=site_id,
            alarm_raised_time=alarm_time,
        )
        noise.append((offset, alarm))
    return noise


def build_dataset(
    seed: int = 42,
    faults: int = 20,
    noise_ratio: float = 0.3,
    concurrent: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    topology = build_topology(seed=seed, small=True)
    base = datetime(2026, 1, 1, tzinfo=UTC)

    all_alarms: list[tuple[float, dict[str, Any]]] = []
    truth: list[dict[str, Any]] = []

    for k in range(1, faults + 1):
        fault_seed = seed * 1000 + k
        minutes = 30 * (k // 2 if concurrent else k)
        start = base + timedelta(minutes=minutes)
        cut = fibre_cut(topology, seed=fault_seed, start=start)

        # keep all alarms for the stream
        all_alarms.extend((minutes * 60 + off, a) for off, a in cut)

        # ground-truth uses only non-cleared alarms
        active = [a for _, a in cut if a.get("state") != "cleared"]
        alarm_ids = [a["id"] for _, a in cut]
        root_sites = [a["siteId"] for a in active[:2]]  # first two are ends
        truth.append(
            {
                "fault": f"F{k:02d}",
                "rootSites": root_sites,
                "alarmIds": alarm_ids,
            }
        )

    # add noise
    rng = random.Random(seed)
    fault_alarm_count = sum(len(t["alarmIds"]) for t in truth)
    noise_count = round(noise_ratio * fault_alarm_count)
    if noise_count:
        site_ids = [s.site_id for s in topology.sites if s.kind == "access"] or [
            s.site_id for s in topology.sites
        ]
        dataset_end = max(off for off, _ in all_alarms) if all_alarms else 0
        noise = _generate_noise_alarms(
            rng,
            noise_count,
            site_ids,
            start=base,
            end=base + timedelta(seconds=dataset_end),
        )
        all_alarms.extend(noise)
        for i, (_, alarm) in enumerate(noise):
            truth.append(
                {
                    "fault": f"NOISE-{i}",
                    "rootSites": [alarm["siteId"]],
                    "alarmIds": [alarm["id"]],
                }
            )

    # sort by offset to produce chronological stream
    all_alarms.sort(key=lambda x: x[0])
    stream = [a for _, a in all_alarms]

    return stream, truth


def evaluate(
    alarms: list[dict[str, Any]],
    truth: list[dict[str, Any]],
    gap_seconds: int = 300,
    max_hops: int = 4,
) -> dict[str, Any]:
    incidents = replay(build_topology(seed=42, small=True), alarms, gap_seconds, max_hops)

    # map alarm id -> incident
    alarm_to_incident: dict[str, dict[str, Any]] = {}
    for inc in incidents:
        for aid in inc.get("alarmIds", []):
            alarm_to_incident[aid] = inc

    real_truth = [t for t in truth if not t["fault"].startswith("NOISE")]
    noise_truth = [t for t in truth if t["fault"].startswith("NOISE")]

    # helpers
    def main_incident(t: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
        counts: Counter = Counter()
        for aid in t["alarmIds"]:
            inc = alarm_to_incident.get(aid)
            if inc:
                counts[inc["id"]] += 1
        if not counts:
            return None, 0
        main_id, main_cnt = counts.most_common(1)[0]
        return next(inc for inc in incidents if inc["id"] == main_id), main_cnt

    fault_match = 0
    purity_sum = 0.0
    completeness_sum = 0.0
    split_faults = 0
    merged_faults = 0
    noise_absorbed = 0

    incident_to_faults: dict[str, list[dict[str, Any]]] = {}
    for t in real_truth:
        inc, cnt = main_incident(t)
        if inc is None:
            continue
        incident_to_faults.setdefault(inc["id"], []).append(t)
        if inc["rootSiteId"] in t["rootSites"]:
            fault_match += 1
        purity_sum += cnt / inc.get("alarmCount", 1)
        completeness_sum += cnt / len(t["alarmIds"])
        if len([aid for aid in t["alarmIds"] if alarm_to_incident.get(aid) != inc]) > 0:
            split_faults += 1

    for faults in incident_to_faults.values():
        if len(faults) > 1:
            merged_faults += len(faults) - 1

    for n in noise_truth:
        for aid in n["alarmIds"]:
            inc = alarm_to_incident.get(aid)
            if inc and any(
                t["fault"].startswith("F") and inc["id"] == main_incident(t)[0]["id"]
                for t in real_truth
            ):
                noise_absorbed += 1
                break

    total_faults = len(real_truth)
    results: dict[str, Any] = {
        "alarms": len(alarms),
        "incidents": len(incidents),
        "compressionRatio": round(compression_ratio(len(alarms), len(incidents)), 2),
        "faults": total_faults,
        "rootMatchRate": round(fault_match / total_faults, 3) if total_faults else 0.0,
        "purity": round(purity_sum / total_faults, 3) if total_faults else 0.0,
        "completeness": round(completeness_sum / total_faults, 3) if total_faults else 0.0,
        "splitFaults": split_faults,
        "mergedFaults": merged_faults,
        "noiseAbsorbed": noise_absorbed,
        "deterministic": replay(
            build_topology(seed=42, small=True),
            list(alarms),
            gap_seconds,
            max_hops,
        )
        == replay(
            build_topology(seed=42, small=True),
            (lambda a: (random.Random(7).shuffle(a), a)[1])(list(alarms)),
            gap_seconds,
            max_hops,
        ),
    }
    return results


def render_report(results: list[tuple[str, dict[str, Any]]]) -> str:
    header = (
        "# RCA report\n\nSynthetic data only; this file is generated by `incident-eval`.\n\n"
        "## Incident compression (W13)\n\n"
    )
    method = (
        "Synthetic fibre-cut faults are generated with `netgen`. "
        "Concurrent pairs are injected, 30 % single-alarm noise is added, "
        "and clustering uses a session gap and a max-hop limit.\n\n"
    )
    table_header = (
        "| Scenario | Alarms | Incidents | Compression | Root match | Purity | Completeness "
        "| Split | Merged | Noise absorbed | Deterministic |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for name, data in results:
        rows.append(
            f"| {name} | {data['alarms']} | {data['incidents']} | {data['compressionRatio']:.2f} | "
            f"{data['rootMatchRate'] * 100:.1f}% | {data['purity'] * 100:.1f}% | "
            f"{data['completeness'] * 100:.1f}% | "
            f"{data['splitFaults']} | {data['mergedFaults']} | "
            f"{data['noiseAbsorbed']} | {data['deterministic']} |"
        )
    table = "\n".join([table_header.rstrip("\n")] + rows) + "\n"
    reproducibility = (
        "\n**How to reproduce**\n\n```sh\nuv run incident-eval --out evals/rca_report.md\n```\n"
    )
    notes = (
        "\n**Reading the numbers**\n\n"
        "- Compression = alarms / incidents. Root match = share of faults whose main incident "
        "has one end of the cut link as root.\n"
        "- The small topology has few hops between sites, so simultaneous cuts often fall "
        "within one relation and merge (Merged). This is a known limit of time + topology "
        "clustering; Phase 2 RCA should split using link-path evidence.\n"
        "- Noise absorbed = single warning alarms close in time and topology to a fault.\n"
    )
    return header + method + table + notes + reproducibility


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--faults", type=int, default=20)
    parser.add_argument("--noise", type=float, default=0.3)
    parser.add_argument("--gap", type=int, default=300)
    parser.add_argument("--hops", type=int, default=4)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    scenarios = [
        ("sequential", False, args.gap),
        ("concurrent pairs", True, args.gap),
        ("concurrent, gap 60s", True, 60),
    ]

    reports: list[tuple[str, dict[str, Any]]] = []
    for name, concurrent, gap in scenarios:
        alarms, truth = build_dataset(
            seed=args.seed,
            faults=args.faults,
            noise_ratio=args.noise,
            concurrent=concurrent,
        )
        res = evaluate(alarms, truth, gap_seconds=gap, max_hops=args.hops)
        reports.append((name, res))

    if args.json:
        print(json.dumps(dict(reports), indent=2))
    else:
        print(render_report(reports))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_report(reports), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
