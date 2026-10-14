"""CLI for netgen topology and KPI generation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from netgen.kpis import generate_kpis
from netgen.topology import build_topology


def _write_json(data: dict, out: str) -> None:
    """Write JSON to file or stdout."""
    if out == "-":
        json.dump(data, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)


def _write_jsonl(records: list[dict], out: str) -> None:
    """Write JSON lines to file or stdout."""
    if out == "-":
        for rec in records:
            json.dump(rec, sys.stdout, sort_keys=True)
            sys.stdout.write("\n")
    else:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for rec in records:
                json.dump(rec, f, sort_keys=True)
                f.write("\n")


def cmd_topology(args: argparse.Namespace) -> int:
    """Handle topology command."""
    topology = build_topology(seed=args.seed, small=not args.full)
    _write_json(topology.to_dict(), args.out)
    return 0


def cmd_kpis(args: argparse.Namespace) -> int:
    """Handle KPI generation command."""
    topology = build_topology(seed=args.seed, small=not args.full)
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=args.days)

    records = list(generate_kpis(topology, args.seed, start, end, step_minutes=15))
    _write_jsonl(records, args.out)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="netgen", description="Synthetic telecom topology and KPI generator"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Topology subcommand
    topo_parser = subparsers.add_parser("topology", help="Generate network topology")
    topo_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    topo_parser.add_argument(
        "--full", action="store_true", help="Generate full topology (60 sites)"
    )
    topo_parser.add_argument(
        "--out",
        default="data/topology.json",
        help="Output file (default: data/topology.json, '-' for stdout)",
    )
    topo_parser.set_defaults(func=cmd_topology)

    # KPI subcommand
    kpi_parser = subparsers.add_parser("kpis", help="Generate KPI samples")
    kpi_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    kpi_parser.add_argument(
        "--days", type=int, default=1, help="Number of days to generate (default: 1)"
    )
    kpi_parser.add_argument("--full", action="store_true", help="Use full topology (60 sites)")
    kpi_parser.add_argument("--out", default="-", help="Output file (default: stdout)")
    kpi_parser.set_defaults(func=cmd_kpis)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
