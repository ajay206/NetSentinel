#!/usr/bin/env python3
"""W23: turn Locust's --csv stats + a replica log into loadtest/report.md (stdlib only)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


def main(prefix: str, replicas_log: str, out: str) -> int:
    rows = list(csv.DictReader(open(f"{prefix}_stats.csv", newline="")))
    replicas = Path(replicas_log).read_text().split() if Path(replicas_log).exists() else []
    lines = [
        "# Load test report (k3d, synthetic data)",
        "",
        "Measured by `make k3d-load`; numbers are from this run only.",
        "",
        "| Endpoint | Requests | Failures | RPS | p50 ms | p95 ms | p99 ms |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['Name']} | {r['Request Count']} | {r['Failure Count']} | "
            f"{float(r['Requests/s']):.1f} | {r['50%']} | {r['95%']} | {r['99%']} |"
        )
    if replicas:
        nums = [int(x) for x in replicas if x.isdigit()]
        lines += [
            "",
            f"copilot-orchestrator replicas during the run: min {min(nums)}, max {max(nums)} "
            f"(sampled every 10 s: {' '.join(map(str, nums))})",
        ]
    Path(out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
