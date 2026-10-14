"""Tests for netgen-simulator CLI."""

from __future__ import annotations

import argparse
import json
from unittest.mock import AsyncMock, patch

import pytest
from netgen_simulator.cli import parse_speed, run_simulation


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
