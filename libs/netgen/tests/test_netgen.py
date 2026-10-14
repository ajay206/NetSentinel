"""Tests for netgen library."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from netgen import SEVERITIES, build_topology, fibre_cut, make_alarm


def test_topology_determinism() -> None:
    """Same seed produces identical topology."""
    t1 = build_topology(seed=42, n_sites=12)
    t2 = build_topology(seed=42, n_sites=12)
    assert t1.sites == t2.sites
    assert t1.links == t2.links


def test_topology_structure() -> None:
    """Topology has correct structure: core -> agg -> cell."""
    topo = build_topology(seed=123, n_sites=12)
    assert len(topo.sites) == 12
    assert len(topo.links) == 11  # tree with 12 nodes has 11 edges

    kinds = [s.kind for s in topo.sites]
    assert "core" in kinds
    assert "agg" in kinds
    assert "cell" in kinds

    # All links are fibre
    for link in topo.links:
        assert link.kind == "fibre"


def test_make_alarm_schema() -> None:
    """make_alarm returns dict with all required camelCase keys."""
    import random

    rng = random.Random(999)
    alarm = make_alarm(
        rng=rng,
        alarm_type="communicationsAlarm",
        perceived_severity="critical",
        probable_cause="lossOfSignal",
        specific_problem="LOS",
        alarmed_object_id="SITE-001",
        site_id="SITE-001",
    )

    required_keys = {
        "id",
        "href",
        "alarmType",
        "perceivedSeverity",
        "probableCause",
        "specificProblem",
        "alarmedObject",
        "siteId",
        "alarmRaisedTime",
        "state",
        "sourceSystemId",
        "@type",
    }
    assert set(alarm.keys()) == required_keys
    assert alarm["href"] == f"/alarm/{alarm['id']}"
    assert alarm["@type"] == "Alarm"
    assert alarm["sourceSystemId"] == "netgen-simulator"
    assert alarm["state"] == "raised"
    # Validate UUID format
    import uuid

    uuid.UUID(alarm["id"])
    # Validate ISO-8601 with Z
    assert alarm["alarmRaisedTime"].endswith("Z")


def test_make_alarm_invalid_severity() -> None:
    """Invalid severity raises ValueError."""
    import random

    rng = random.Random(1)
    with pytest.raises(ValueError, match="Invalid severity"):
        make_alarm(
            rng=rng,
            alarm_type="test",
            perceived_severity="invalid",
            probable_cause="test",
            specific_problem="test",
            alarmed_object_id="SITE-001",
        )


def test_fibre_cut_determinism() -> None:
    """Same seed produces identical alarm sequence."""
    topo = build_topology(seed=42, n_sites=12)
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    alarms1 = fibre_cut(topo, seed=42, start=start)
    alarms2 = fibre_cut(topo, seed=42, start=start)

    assert len(alarms1) == len(alarms2)
    for (off1, a1), (off2, a2) in zip(alarms1, alarms2, strict=True):
        assert off1 == off2
        assert a1 == a2


def test_fibre_cut_severities_valid() -> None:
    """All generated alarms have valid severities."""
    topo = build_topology(seed=42, n_sites=12)
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    alarms = fibre_cut(topo, seed=42, start=start)
    for _, alarm in alarms:
        assert alarm["perceivedSeverity"] in SEVERITIES


def test_fibre_cut_offsets_sorted() -> None:
    """Alarm offsets are non-decreasing."""
    topo = build_topology(seed=42, n_sites=12)
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    alarms = fibre_cut(topo, seed=42, start=start)
    offsets = [off for off, _ in alarms]
    assert offsets == sorted(offsets)


def test_fibre_cut_cleared_at_end() -> None:
    """Scenario ends with cleared alarms."""
    topo = build_topology(seed=42, n_sites=12)
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    alarms = fibre_cut(topo, seed=42, start=start)
    # Last several alarms should be cleared
    cleared_count = sum(1 for _, a in alarms if a["perceivedSeverity"] == "cleared")
    assert cleared_count >= 2  # At least the two LOS alarms cleared


def test_fibre_cut_has_critical_los() -> None:
    """Scenario starts with critical LOS on both ends."""
    topo = build_topology(seed=42, n_sites=12)
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    alarms = fibre_cut(topo, seed=42, start=start)
    # First two alarms should be critical LOS at offset 0
    assert alarms[0][0] == 0.0
    assert alarms[1][0] == 0.0
    assert alarms[0][1]["perceivedSeverity"] == "critical"
    assert alarms[0][1]["specificProblem"] == "LOS"
    assert alarms[1][1]["perceivedSeverity"] == "critical"
    assert alarms[1][1]["specificProblem"] == "LOS"
    # Different sites
    assert alarms[0][1]["siteId"] != alarms[1][1]["siteId"]


def test_fibre_cut_downstream_cells() -> None:
    """Sympathetic alarms appear on downstream cells."""
    topo = build_topology(seed=42, n_sites=12)
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)

    alarms = fibre_cut(topo, seed=42, start=start)
    cell_alarms = [a for _, a in alarms if topo.site_by_id[a["siteId"]].kind == "cell"]
    assert len(cell_alarms) > 0
    # Should have multiple severity levels on cells
    cell_severities = {a["perceivedSeverity"] for a in cell_alarms}
    assert "major" in cell_severities or "minor" in cell_severities
