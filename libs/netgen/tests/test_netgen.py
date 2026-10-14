"""Tests for netgen topology, alarms, and KPIs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from netgen.alarms import fibre_cut, make_alarm
from netgen.kpis import KPI_BOUNDS, generate_kpis, kpi_value
from netgen.topology import build_topology


def _sha256_of_dict(d: dict) -> str:
    """Compute SHA256 of JSON-serialized dict with sorted keys."""
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


class TestTopologyDeterminism:
    """Test topology determinism and structure."""

    def test_same_seed_produces_identical_topology(self) -> None:
        t1 = build_topology(seed=42, small=True)
        t2 = build_topology(seed=42, small=True)
        assert _sha256_of_dict(t1.to_dict()) == _sha256_of_dict(t2.to_dict())

    def test_different_seed_produces_different_topology(self) -> None:
        t1 = build_topology(seed=42, small=True)
        t2 = build_topology(seed=43, small=True)
        assert _sha256_of_dict(t1.to_dict()) != _sha256_of_dict(t2.to_dict())

    def test_small_topology_counts(self) -> None:
        t = build_topology(seed=42, small=True)
        d = t.to_dict()
        assert d["counts"]["regions"] == 3
        assert d["counts"]["sites"] == 12
        # 2 core + 3 hubs + 7 access = 12 sites
        kinds = [s["kind"] for s in d["sites"]]
        assert kinds.count("core") == 2
        assert kinds.count("hub") == 3
        assert kinds.count("access") == 7
        # Nodes: ~1-2 per site
        assert 12 <= d["counts"]["nodes"] <= 24
        # Cells: 3 per node
        assert d["counts"]["cells"] == d["counts"]["nodes"] * 3
        # Links: core-core(1) + core-hub(2*3=6) + ring(3) + access(7) = 17
        assert (
            d["counts"]["links"] >= 14
        )  # 7 core uplinks + 7 access; 1 hub per region means no ring

    def test_full_topology_counts(self) -> None:
        t = build_topology(seed=42, small=False)
        d = t.to_dict()
        assert d["counts"]["regions"] == 3
        assert d["counts"]["sites"] == 60
        kinds = [s["kind"] for s in d["sites"]]
        assert kinds.count("core") == 2
        assert kinds.count("hub") == 9  # 3 per region
        assert kinds.count("access") == 49
        # Nodes: ~3 per site -> 150-210
        assert 150 <= d["counts"]["nodes"] <= 210
        # Cells: 3 per node -> 450-630
        assert 450 <= d["counts"]["cells"] <= 630

    def test_all_access_sites_reachable(self) -> None:
        t = build_topology(seed=42, small=False)
        # Every access site should be in children of some hub
        access_sites = [s for s in t.sites if s.kind == "access"]
        hub_sites = [s for s in t.sites if s.kind == "hub"]
        all_children = []
        for hub in hub_sites:
            all_children.extend(t.children.get(hub.site_id, []))
        for access in access_sites:
            assert access.site_id in all_children

    def test_site_ids_are_sequential(self) -> None:
        t = build_topology(seed=42, small=True)
        site_ids = [s.site_id for s in t.sites]
        expected = [f"SITE-{i:03d}" for i in range(1, 13)]
        assert site_ids == expected

    def test_regions_stacked_north_to_south(self) -> None:
        t = build_topology(seed=42, small=False)
        # Core sites deliberately sit in the centre of the map, so only hubs/access count
        north_lats = [s.lat for s in t.sites if s.kind != "core" and s.region == "North"]
        central_lats = [s.lat for s in t.sites if s.kind != "core" and s.region == "Central"]
        south_lats = [s.lat for s in t.sites if s.kind != "core" and s.region == "South"]
        assert min(north_lats) > max(central_lats)
        assert min(central_lats) > max(south_lats)

    def test_coordinates_in_bounds(self) -> None:
        t = build_topology(seed=42, small=False)
        for s in t.sites:
            assert 12.0 <= s.lat <= 28.0
            assert 72.0 <= s.lon <= 88.0

    def test_nodes_and_cells_structure(self) -> None:
        t = build_topology(seed=42, small=True)
        for site in t.sites:
            assert len(site.nodes) >= 1
            for node in site.nodes:
                assert node.kind in ("gNB", "eNB", "router")
                assert len(node.cells) == 3
                for cell in node.cells:
                    assert cell.startswith(f"{node.node_id}-C")


class TestAlarms:
    """Test alarm generation."""

    def test_make_alarm_basic(self) -> None:
        rng = __import__("random").Random(42)
        alarm = make_alarm(
            rng=rng,
            alarm_type="communicationsAlarm",
            perceived_severity="critical",
            probable_cause="lossOfSignal",
            specific_problem="LOS",
            alarmed_object_id="SITE-001",
            site_id="SITE-001",
        )
        assert alarm["@type"] == "Alarm"
        assert alarm["perceivedSeverity"] == "critical"
        assert alarm["siteId"] == "SITE-001"
        assert alarm["state"] == "raised"

    def test_make_alarm_invalid_severity(self) -> None:
        rng = __import__("random").Random(42)
        with pytest.raises(ValueError):
            make_alarm(
                rng=rng,
                alarm_type="test",
                perceived_severity="invalid",
                probable_cause="test",
                specific_problem="test",
                alarmed_object_id="SITE-001",
            )

    def test_fibre_cut_uses_existing_site_ids(self) -> None:
        t = build_topology(seed=42, small=True)
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        alarms = fibre_cut(t, seed=123, start=start)
        site_ids = {s.site_id for s in t.sites}
        for _, alarm in alarms:
            assert alarm["siteId"] in site_ids
            assert alarm["alarmedObject"]["id"] in site_ids

    def test_fibre_cut_offsets_sorted(self) -> None:
        t = build_topology(seed=42, small=True)
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        alarms = fibre_cut(t, seed=123, start=start)
        offsets = [offset for offset, _ in alarms]
        assert offsets == sorted(offsets)

    def test_fibre_cut_cleared_last(self) -> None:
        t = build_topology(seed=42, small=True)
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        alarms = fibre_cut(t, seed=123, start=start)
        # Last alarms should be cleared
        last_severities = [alarm["perceivedSeverity"] for _, alarm in alarms[-3:]]
        assert all(s == "cleared" for s in last_severities)

    def test_fibre_cut_deterministic(self) -> None:
        t = build_topology(seed=42, small=True)
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        alarms1 = fibre_cut(t, seed=123, start=start)
        alarms2 = fibre_cut(t, seed=123, start=start)
        assert len(alarms1) == len(alarms2)
        for (o1, a1), (o2, a2) in zip(alarms1, alarms2, strict=True):
            assert o1 == o2
            assert a1["id"] == a2["id"]
            assert a1["alarmRaisedTime"] == a2["alarmRaisedTime"]


class TestKPIs:
    """Test KPI generation."""

    def test_kpi_value_within_bounds(self) -> None:
        for kpi_name, (lo, hi) in KPI_BOUNDS.items():
            val = kpi_value(
                42,
                "SITE-001-N1-C1",
                kpi_name,
                datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
                datetime(2024, 1, 1, tzinfo=UTC),
            )
            assert lo <= val <= hi, f"{kpi_name}={val} not in [{lo}, {hi}]"

    def test_kpi_determinism(self) -> None:
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        start = datetime(2024, 1, 1, tzinfo=UTC)
        v1 = kpi_value(42, "SITE-001-N1-C1", "dlThroughputMbps", ts, start)
        v2 = kpi_value(42, "SITE-001-N1-C1", "dlThroughputMbps", ts, start)
        assert v1 == v2

    def test_kpi_different_seeds_different(self) -> None:
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        start = datetime(2024, 1, 1, tzinfo=UTC)
        v1 = kpi_value(42, "SITE-001-N1-C1", "dlThroughputMbps", ts, start)
        v2 = kpi_value(43, "SITE-001-N1-C1", "dlThroughputMbps", ts, start)
        assert v1 != v2

    def test_generate_kpis_small_one_day(self) -> None:
        t = build_topology(seed=42, small=True)
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(days=1)
        records = list(generate_kpis(t, seed=42, start=start, end=end, step_minutes=15))
        # 12 sites * ~1.5 nodes * 3 cells = ~54 cells * 96 intervals = ~5184 records
        assert len(records) > 0
        for rec in records:
            assert rec["@type"] == "KpiSample"
            assert "sampleId" in rec
            assert rec["siteId"].startswith("SITE-")
            assert rec["nodeId"].startswith("SITE-")
            assert rec["cellId"].startswith("SITE-")
            assert rec["region"] in ("North", "Central", "South")
            assert rec["granularitySec"] == 900
            # Check timestamp alignment
            ts = datetime.fromisoformat(rec["timestamp"].replace("Z", "+00:00"))
            assert ts.minute % 15 == 0
            assert ts.second == 0
            # Check KPI bounds
            for kpi_name, val in rec["kpis"].items():
                lo, hi = KPI_BOUNDS[kpi_name]
                assert lo <= val <= hi, f"{kpi_name}={val} not in [{lo}, {hi}]"

    def test_kpi_records_deterministic(self) -> None:
        t = build_topology(seed=42, small=True)
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        end = start + timedelta(hours=1)
        records1 = list(generate_kpis(t, seed=42, start=start, end=end, step_minutes=15))
        records2 = list(generate_kpis(t, seed=42, start=start, end=end, step_minutes=15))
        assert len(records1) == len(records2)
        for r1, r2 in zip(records1, records2, strict=True):
            assert r1["sampleId"] == r2["sampleId"]
            assert r1["kpis"] == r2["kpis"]

    def test_kpis_seasonality_peak_vs_trough(self) -> None:
        """Mean dlThroughput at 14:30 UTC (peak) > at 22:30 UTC (trough)."""
        t = build_topology(seed=42, small=True)
        # Use a single day, collect values at peak and trough hours
        peak_vals = []
        trough_vals = []
        for day in range(7):  # Week to average out weekly effect
            base = datetime(2024, 1, 1 + day, tzinfo=UTC)
            peak_ts = base.replace(hour=14, minute=30)
            trough_ts = base.replace(hour=22, minute=30)
            for site in t.sites:
                for node in site.nodes:
                    for cell_id in node.cells:
                        peak_vals.append(kpi_value(42, cell_id, "dlThroughputMbps", peak_ts, base))
                        trough_vals.append(
                            kpi_value(42, cell_id, "dlThroughputMbps", trough_ts, base)
                        )
        assert sum(peak_vals) / len(peak_vals) > sum(trough_vals) / len(trough_vals)

    def test_kpis_weekend_reduction(self) -> None:
        """Weekend values should be ~15% lower than weekdays."""
        t = build_topology(seed=42, small=True)
        # Monday vs Saturday
        mon = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)  # Monday
        sat = datetime(2024, 1, 6, 12, 0, tzinfo=UTC)  # Saturday
        mon_vals = []
        sat_vals = []
        for site in t.sites:
            for node in site.nodes:
                for cell_id in node.cells:
                    mon_vals.append(kpi_value(42, cell_id, "dlThroughputMbps", mon, mon))
                    sat_vals.append(kpi_value(42, cell_id, "dlThroughputMbps", sat, sat))
        mon_mean = sum(mon_vals) / len(mon_vals)
        sat_mean = sum(sat_vals) / len(sat_vals)
        # Weekend should be ~15% lower (allow some tolerance for noise)
        assert sat_mean < mon_mean * 0.95


class TestCLI:
    """Test CLI commands (smoke tests)."""

    def test_topology_cli_small(self, tmp_path) -> None:
        import argparse

        from netgen.cli import cmd_topology

        out_file = tmp_path / "topo.json"
        args = argparse.Namespace(seed=42, full=False, out=str(out_file))
        assert cmd_topology(args) == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["counts"]["sites"] == 12

    def test_topology_cli_full(self, tmp_path) -> None:
        import argparse

        from netgen.cli import cmd_topology

        out_file = tmp_path / "topo_full.json"
        args = argparse.Namespace(seed=42, full=True, out=str(out_file))
        assert cmd_topology(args) == 0
        data = json.loads(out_file.read_text())
        assert data["counts"]["sites"] == 60

    def test_kpis_cli(self, tmp_path) -> None:
        import argparse

        from netgen.cli import cmd_kpis

        out_file = tmp_path / "kpis.jsonl"
        args = argparse.Namespace(seed=42, days=1, full=False, out=str(out_file))
        assert cmd_kpis(args) == 0
        assert out_file.exists()
        lines = out_file.read_text().strip().split("\n")
        assert len(lines) > 0
        first = json.loads(lines[0])
        assert first["@type"] == "KpiSample"
        assert "kpis" in first
