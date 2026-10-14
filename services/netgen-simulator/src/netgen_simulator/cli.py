"""CLI for netgen-simulator."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import UTC, datetime

from aiokafka import AIOKafkaProducer
from netgen import build_topology, fibre_cut

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
) -> None:
    """Run the alarm simulation."""
    iteration = 0
    while True:
        current_seed = seed + iteration
        logger.info("Starting simulation iteration %d with seed %d", iteration, current_seed)

        topology = build_topology(seed=current_seed, n_sites=12)
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
                # Wait (scaled by speed) until this alarm's scenario offset, then send it
                delta = (offset - prev_offset) / speed
                if delta > 0:
                    await asyncio.sleep(delta)
                prev_offset = offset
                # Refresh alarmRaisedTime to now at send time
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


def main() -> None:
    """Main entry point."""

    def handler(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handler)

    parser = argparse.ArgumentParser(prog="netgen-sim", description="NetGen Alarm Simulator")
    parser.add_argument(
        "command",
        choices=["run"],
        help="Command to execute",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument(
        "--scenario",
        choices=["fibre_cut"],
        default="fibre_cut",
        help="Scenario to simulate (default: fibre_cut)",
    )
    parser.add_argument(
        "--speed",
        type=parse_speed,
        default="60x",
        help="Simulation speed multiplier (default: 60x)",
    )
    parser.add_argument(
        "--bootstrap",
        default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
        help="Kafka bootstrap servers (default: localhost:9092 or KAFKA_BOOTSTRAP env)",
    )
    parser.add_argument(
        "--topic",
        default="alarms.raw",
        help="Kafka topic to publish to (default: alarms.raw)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON lines to stdout instead of sending to Kafka",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Repeat scenario forever with incrementing seed",
    )

    args = parser.parse_args()

    if args.command == "run":
        try:
            asyncio.run(
                run_simulation(
                    seed=args.seed,
                    scenario=args.scenario,
                    speed=args.speed,
                    bootstrap=args.bootstrap,
                    topic=args.topic,
                    dry_run=args.dry_run,
                    loop=args.loop,
                )
            )
        except KeyboardInterrupt:
            logger.info("Simulation stopped by user")
            sys.exit(0)
        except Exception as e:
            logger.exception("Simulation failed: %s", e)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
