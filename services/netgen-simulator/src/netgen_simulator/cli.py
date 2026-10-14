"""CLI for netgen-simulator."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import UTC, datetime, timedelta

from aiokafka import AIOKafkaProducer
from netgen import build_topology, fibre_cut, generate_kpis
from netgen.kpis import KPI_NAMES, _deterministic_uuid, kpi_value

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("netgen-simulator")


def parse_speed(value: str) -> float:
    """Parse speed string like '60x' to float 60.0."""
    if not value.endswith("x"):
        raise argparse.ArgumentTypeError(f"Speed must end with 'x', got: {value}")
    try:
        speed = float(value[:-1])
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid speed value: {value}") from e
    if speed <= 0:
        raise argparse.ArgumentTypeError("Speed must be positive")
    return speed


async def run_simulation(
    seed: int,
    scenario: str,
    speed: float,
    bootstrap: str,
    topic: str,
    dry_run: bool,
    loop: bool,
    small: bool = True,
) -> None:
    """Run the alarm simulation."""
    topology = build_topology(seed=seed, small=small)
    iteration = 0
    while True:
        current_seed = seed + iteration
        logger.info("Starting simulation iteration %d with seed %d", iteration, current_seed)

        start_time = datetime.now(UTC)

        if scenario == "fibre_cut":
            alarms = fibre_cut(topology, seed=current_seed, start=start_time)
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        producer: AIOKafkaProducer | None = None
        if not dry_run:
            producer = AIOKafkaProducer(
                bootstrap_servers=bootstrap,
                value_serializer=lambda v: json.dumps(v, default=str).encode(),
                key_serializer=lambda k: k.encode() if k else None,
            )
            await producer.start()
            logger.info("Connected to Kafka at %s", bootstrap)

        try:
            prev_offset = 0.0
            for offset, alarm in alarms:
                delta = (offset - prev_offset) / speed
                if delta > 0:
                    await asyncio.sleep(delta)
                prev_offset = offset
                alarm["alarmRaisedTime"] = (
                    datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
                )
                site_id = alarm["siteId"]
                if dry_run:
                    print(json.dumps(alarm, default=str), flush=True)
                else:
                    assert producer is not None
                    await producer.send_and_wait(topic, value=alarm, key=site_id)
                    logger.debug("Sent alarm %s for site %s", alarm["id"], site_id)

            logger.info("Completed iteration %d with %d alarms", iteration, len(alarms))
        finally:
            if producer:
                await producer.stop()

        if not loop:
            break
        iteration += 1


def _floor_to_15min(dt: datetime) -> datetime:
    """Floor datetime to 15‑minute boundary."""
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)


async def run_kpis(
    seed: int,
    days: float,
    small: bool,
    bootstrap: str,
    topic: str,
    dry_run: bool,
    follow: bool,
    interval: int,
) -> None:
    """Run KPI simulation with backfill and optional live follow mode."""
    logger.info(
        "Starting KPI simulation with seed=%d, days=%.1f, small=%s, follow=%s",
        seed,
        days,
        small,
        follow,
    )

    topology = build_topology(seed=seed, small=small)

    producer: AIOKafkaProducer | None = None
    if not dry_run:
        producer = AIOKafkaProducer(
            bootstrap_servers=bootstrap,
            value_serializer=lambda v: json.dumps(v, default=str).encode(),
            key_serializer=lambda k: k.encode() if k else None,
        )
        await producer.start()
        logger.info("Connected to Kafka at %s", bootstrap)

    try:
        # ---------- Backfill ----------
        end_time = _floor_to_15min(datetime.now(UTC))
        start_time = end_time - timedelta(days=days)
        logger.info("Backfill period: %s → %s", start_time.isoformat(), end_time.isoformat())

        total_sent = 0
        batch = 0
        async for sample in _kpi_backfill_generator(topology, seed, start_time, end_time):
            if dry_run:
                print(json.dumps(sample, default=str), flush=True)
            else:
                assert producer is not None
                await producer.send(topic, value=sample, key=sample["cellId"])
                batch += 1
                if batch >= 500:
                    await producer.flush()
                    batch = 0
            total_sent += 1

        if not dry_run and producer is not None and batch > 0:
            await producer.flush()
        logger.info("Backfill complete, sent %d KPI samples", total_sent)

        # ---------- Follow mode ----------
        if follow:
            logger.info("Entering follow mode, publishing every %d seconds", interval)
            while True:
                now = datetime.now(UTC).replace(microsecond=0)
                for sample in _kpi_live_samples(topology, seed, now):
                    if dry_run:
                        print(json.dumps(sample, default=str), flush=True)
                    else:
                        assert producer is not None
                        await producer.send_and_wait(topic, value=sample, key=sample["cellId"])
                logger.debug("Published live KPI batch at %s", now.isoformat())
                await asyncio.sleep(interval)
    finally:
        if producer:
            await producer.stop()


async def _kpi_backfill_generator(
    topology,
    seed: int,
    start: datetime,
    end: datetime,
):
    """Yield KPI samples for backfill using generate_kpis."""
    # generate_kpis yields dicts; we wrap in async generator for uniform handling
    for sample in generate_kpis(topology, seed, start, end):
        yield sample


def _kpi_live_samples(topology, seed: int, timestamp: datetime):
    """Generate a single KPI sample per cell for the given timestamp."""
    samples = []
    iso_ts = timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")
    for site in topology.sites:
        for node in site.nodes:
            for cell_id in node.cells:
                kpis = {
                    name: round(kpi_value(seed, cell_id, name, timestamp, timestamp), 3)
                    for name in KPI_NAMES
                }
                sample = {
                    "@type": "KpiSample",
                    "sampleId": _deterministic_uuid(seed, cell_id, iso_ts),
                    "siteId": site.site_id,
                    "nodeId": node.node_id,
                    "cellId": cell_id,
                    "region": site.region,
                    "timestamp": iso_ts,
                    "granularitySec": 900,
                    "kpis": kpis,
                }
                samples.append(sample)
    return samples


def main() -> None:
    """Main entry point."""

    def handler(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handler)

    parser = argparse.ArgumentParser(prog="netgen-sim", description="NetGen Simulator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- run (alarms) ----
    run_parser = subparsers.add_parser("run", help="Run alarm simulation")
    run_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    run_parser.add_argument(
        "--scenario",
        choices=["fibre_cut"],
        default="fibre_cut",
        help="Scenario to simulate (default: fibre_cut)",
    )
    run_parser.add_argument(
        "--speed",
        type=parse_speed,
        default="60x",
        help="Simulation speed multiplier (default: 60x)",
    )
    run_parser.add_argument(
        "--bootstrap",
        default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
        help="Kafka bootstrap servers (default: localhost:9092 or KAFKA_BOOTSTRAP env)",
    )
    run_parser.add_argument(
        "--topic",
        default="alarms.raw",
        help="Kafka topic to publish to (default: alarms.raw)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON lines to stdout instead of sending to Kafka",
    )
    run_parser.add_argument(
        "--loop",
        action="store_true",
        help="Repeat scenario forever with incrementing seed",
    )
    run_parser.add_argument(
        "--full",
        action="store_true",
        help="Use full topology (default: small)",
    )

    # ---- kpis ----
    kpis_parser = subparsers.add_parser("kpis", help="Run KPI simulation")
    kpis_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    kpis_parser.add_argument(
        "--days", type=float, default=7.0, help="Days of backfill (default: 7)"
    )
    size_group = kpis_parser.add_mutually_exclusive_group()
    size_group.add_argument(
        "--small", action="store_true", default=True, help="Use small topology (default)"
    )
    size_group.add_argument("--full", action="store_true", help="Use full topology")
    kpis_parser.add_argument(
        "--bootstrap",
        default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
        help="Kafka bootstrap servers (default: localhost:9092 or KAFKA_BOOTSTRAP env)",
    )
    kpis_parser.add_argument(
        "--topic",
        default="kpis",
        help="Kafka topic to publish to (default: kpis)",
    )
    kpis_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON lines to stdout instead of sending to Kafka",
    )
    kpis_parser.add_argument(
        "--follow",
        action="store_true",
        help="After backfill, continuously publish live samples",
    )
    kpis_parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Interval in seconds for live samples (default: 5)",
    )

    args = parser.parse_args()

    try:
        if args.command == "run":
            asyncio.run(
                run_simulation(
                    seed=args.seed,
                    scenario=args.scenario,
                    speed=args.speed,
                    bootstrap=args.bootstrap,
                    topic=args.topic,
                    dry_run=args.dry_run,
                    loop=args.loop,
                    small=not args.full,
                )
            )
        elif args.command == "kpis":
            asyncio.run(
                run_kpis(
                    seed=args.seed,
                    days=args.days,
                    small=not args.full,
                    bootstrap=args.bootstrap,
                    topic=args.topic,
                    dry_run=args.dry_run,
                    follow=args.follow,
                    interval=args.interval,
                )
            )
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Simulation stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.exception("Simulation failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
