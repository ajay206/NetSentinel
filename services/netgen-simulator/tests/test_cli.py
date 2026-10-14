"""Tests for netgen-simulator CLI."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from netgen import build_topology
from netgen.kpis import KPI_BOUNDS
from netgen_simulator.cli import _kpi_live_samples, parse_speed, run_kpis, run_simulation


def test_parse_speed_valid() -> None:
    """parse_speed correctly parses valid speed strings."""
    assert parse_speed("1x") == 1.0
    assert parse_speed("60x") == 60.0
    assert parse_speed("0.5x") == 0.5
    assert parse_speed("100x") == 100.0


def test_parse_speed_invalid() -> None:
    """parse_speed rejects invalid formats."""
    with pytest.raises(argparse.ArgumentTypeError, match="must end with 'x'"):
        parse_speed("60")
    with pytest.raises(argparse.ArgumentTypeError, match="must end with 'x'"):
        parse_speed("60X")
    with pytest.raises(argparse.ArgumentTypeError, match="positive"):
        parse_speed("0x")
    with pytest.raises(argparse.ArgumentTypeError, match="positive"):
        parse_speed("-1x")
    with pytest.raises(argparse.ArgumentTypeError, match="Invalid speed"):
        parse_speed("abcx")


@pytest.mark.asyncio
async def test_run_simulation_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    """Dry run prints JSON lines to stdout."""
    # Use huge speed to make it instant
    await run_simulation(
        seed=42,
        scenario="fibre_cut",
        speed=1e9,
        bootstrap="localhost:9092",
        topic="alarms.raw",
        dry_run=True,
        loop=False,
    )

    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert len(lines) > 0

    # Each line should be valid JSON with required keys
    for line in lines:
        alarm = json.loads(line)
        assert "id" in alarm
        assert "perceivedSeverity" in alarm
        assert "siteId" in alarm
        assert alarm["@type"] == "Alarm"


@pytest.mark.asyncio
async def test_run_simulation_invalid_scenario() -> None:
    """Invalid scenario raises ValueError."""
    with pytest.raises(ValueError, match="Unknown scenario"):
        await run_simulation(
            seed=42,
            scenario="invalid_scenario",
            speed=60.0,
            bootstrap="localhost:9092",
            topic="alarms.raw",
            dry_run=True,
            loop=False,
        )


@pytest.mark.asyncio
async def test_run_simulation_kafka_send(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-dry-run sends to Kafka producer."""
    mock_producer = AsyncMock()
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    with patch("netgen_simulator.cli.AIOKafkaProducer", return_value=mock_producer):
        await run_simulation(
            seed=42,
            scenario="fibre_cut",
            speed=1e9,
            bootstrap="localhost:9092",
            topic="alarms.raw",
            dry_run=False,
            loop=False,
        )

    mock_producer.start.assert_awaited_once()
    mock_producer.stop.assert_awaited_once()
    assert mock_producer.send_and_wait.await_count > 0


@pytest.mark.asyncio
async def test_run_kpis_dry_run_backfill(capsys: pytest.CaptureFixture[str]) -> None:
    """KPI dry run backfill prints JSON lines with KPI samples."""
    await run_kpis(
        seed=42,
        days=0.1,
        small=True,
        bootstrap="localhost:9092",
        topic="kpis",
        dry_run=True,
        follow=False,
        interval=5,
    )

    captured = capsys.readouterr()
    lines = captured.out.strip().split("\n")
    assert len(lines) > 0

    # Each line should be valid JSON with required KPI keys
    for line in lines:
        sample = json.loads(line)
        assert "cellId" in sample
        assert "timestamp" in sample
        assert "kpis" in sample
        assert "dlThroughputMbps" in sample["kpis"]
        assert sample["@type"] == "KpiSample"


@pytest.mark.asyncio
async def test_run_kpis_kafka_send(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-dry-run KPI sends to Kafka producer."""
    mock_producer = AsyncMock()
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()
    mock_producer.send = AsyncMock()
    mock_producer.flush = AsyncMock()

    with patch("netgen_simulator.cli.AIOKafkaProducer", return_value=mock_producer):
        await run_kpis(
            seed=42,
            days=0.1,
            small=True,
            bootstrap="localhost:9092",
            topic="kpis",
            dry_run=False,
            follow=False,
            interval=5,
        )

    mock_producer.start.assert_awaited_once()
    mock_producer.stop.assert_awaited_once()
    assert mock_producer.send.await_count > 0
    mock_producer.flush.assert_awaited()


@pytest.mark.asyncio
async def test_run_kpis_follow_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Follow mode publishes live samples periodically."""
    mock_producer = AsyncMock()
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    # Mock asyncio.sleep to raise KeyboardInterrupt after first iteration
    original_sleep = asyncio.sleep
    sleep_count = 0

    async def mock_sleep(delay):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise KeyboardInterrupt
        await original_sleep(0)

    with patch("netgen_simulator.cli.AIOKafkaProducer", return_value=mock_producer):
        with patch("asyncio.sleep", mock_sleep):
            try:
                await run_kpis(
                    seed=42,
                    days=0.01,
                    small=True,
                    bootstrap="localhost:9092",
                    topic="kpis",
                    dry_run=False,
                    follow=True,
                    interval=5,
                )
            except KeyboardInterrupt:
                pass

    assert mock_producer.send_and_wait.await_count > 0
    mock_producer.stop.assert_awaited_once()


# Helper for KPI dry‑run tests
async def _run_kpis_helper(
    *,
    seed: int = 42,
    days: float = 0.1,
    small: bool = True,
    dry_run: bool = True,
) -> list[dict]:
    """Run run_kpis with dry‑run and capture printed JSON lines."""
    import sys
    from io import StringIO

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        await run_kpis(
            seed=seed,
            days=days,
            small=small,
            bootstrap="localhost:9092",
            topic="kpis",
            dry_run=dry_run,
            follow=False,
            interval=5,
        )
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    lines = [ln for ln in output.strip().split("\n") if ln]
    return [json.loads(line) for line in lines]


@pytest.mark.asyncio
async def test_kpis_dry_run_helper_outputs_kpis() -> None:
    """Helper run_kpis returns list of KPI dicts with expected fields."""
    samples = await _run_kpis_helper()
    assert samples, "No KPI samples were produced"
    for sample in samples:
        assert "cellId" in sample
        assert "timestamp" in sample
        assert "kpis" in sample
        assert "dlThroughputMbps" in sample["kpis"]
        assert sample["@type"] == "KpiSample"


def test_kpi_live_samples_structure() -> None:
    """_kpi_live_samples returns one sample per cell with correct structure."""
    topology = build_topology(seed=42, small=True)
    now = datetime.now(UTC).replace(microsecond=0)
    samples = _kpi_live_samples(topology, 42, now)
    assert len(samples) > 0
    for s in samples:
        assert s["timestamp"] == now.isoformat(timespec="seconds").replace("+00:00", "Z")
        assert s["granularitySec"] == 900
        for k, v in s["kpis"].items():
            min_val, max_val = KPI_BOUNDS[k]
            assert min_val <= v <= max_val
