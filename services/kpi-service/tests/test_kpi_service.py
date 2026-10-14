from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ["DISABLE_KAFKA"] = "1"
os.environ["KPI_STORE"] = "memory"

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kpi_service.consumer import BatchWriter
from kpi_service.main import app
from kpi_service.models import KpiRow, parse_sample
from kpi_service.store import MemoryStore


@pytest.fixture(autouse=True)
def reset_store():
    import kpi_service.main as main_module

    main_module._store = None
    main_module._writer = None
    main_module._state = {"connected": False}
    yield


def test_parse_sample_valid():
    raw = {
        "@type": "KpiSample",
        "sampleId": "0192f0c1-2345-7123-abcd-ef0123456789",
        "siteId": "SITE-001",
        "nodeId": "SITE-001-N1",
        "cellId": "SITE-001-N1-C1",
        "region": "North",
        "timestamp": "2026-10-14T09:15:00Z",
        "granularitySec": 900,
        "kpis": {
            "dlThroughputMbps": 314.9,
            "prbUtilPct": 44.6,
            "rrcSetupSuccessPct": 98.4,
            "dropCallRatePct": 0.6,
            "availabilityPct": 99.6,
        },
    }
    row = parse_sample(raw)
    assert row is not None
    assert row.cell_id == "SITE-001-N1-C1"
    assert row.dl_throughput_mbps == 314.9
    assert row.prb_util_pct == 44.6
    assert row.ts.tzinfo == UTC


def test_parse_sample_missing_fields():
    assert parse_sample({"sampleId": "x", "cellId": "c"}) is None
    assert parse_sample({"sampleId": "x", "timestamp": "2026-10-14T09:15:00Z"}) is None
    assert parse_sample({"cellId": "c", "timestamp": "2026-10-14T09:15:00Z"}) is None
    assert (
        parse_sample({"sampleId": "not-uuid", "cellId": "c", "timestamp": "2026-10-14T09:15:00Z"})
        is None
    )
    assert (
        parse_sample(
            {
                "sampleId": "0192f0c1-2345-7123-abcd-ef0123456789",
                "cellId": "c",
                "timestamp": "invalid",
            }
        )
        is None
    )


def test_memory_store_idempotent():
    store = MemoryStore()
    row = KpiRow(
        sample_id=uuid4(),
        ts=datetime(2026, 10, 14, 9, 15, tzinfo=UTC),
        site_id="SITE-001",
        node_id="SITE-001-N1",
        cell_id="SITE-001-N1-C1",
        region="North",
        dl_throughput_mbps=100.0,
        prb_util_pct=50.0,
        rrc_setup_success_pct=99.0,
        drop_call_rate_pct=0.5,
        availability_pct=99.9,
    )
    import asyncio

    count1 = asyncio.run(store.insert_many([row]))
    count2 = asyncio.run(store.insert_many([row]))
    assert count1 == 1
    assert count2 == 0


def test_memory_store_raw_query_ordering_and_filter():
    store = MemoryStore()
    base = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
    rows = [
        KpiRow(
            sample_id=uuid4(),
            ts=base + timedelta(minutes=15 * i),
            site_id="SITE-001",
            node_id="SITE-001-N1",
            cell_id="SITE-001-N1-C1",
            region="North",
            dl_throughput_mbps=float(100 + i * 10),
            prb_util_pct=50.0,
            rrc_setup_success_pct=99.0,
            drop_call_rate_pct=0.5,
            availability_pct=99.9,
        )
        for i in range(4)
    ]
    import asyncio

    asyncio.run(store.insert_many(rows))

    result = asyncio.run(store.query("SITE-001-N1-C1", base, base + timedelta(hours=1), "raw"))
    assert len(result) == 4
    assert result[0]["dlThroughputMbps"] == 100.0
    assert result[3]["dlThroughputMbps"] == 130.0

    result = asyncio.run(
        store.query(
            "SITE-001-N1-C1", base + timedelta(minutes=30), base + timedelta(minutes=45), "raw"
        )
    )
    assert len(result) == 1
    assert result[0]["dlThroughputMbps"] == 120.0


def test_memory_store_1h_bucketing():
    store = MemoryStore()
    base = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
    rows = [
        KpiRow(
            sample_id=uuid4(),
            ts=base + timedelta(minutes=15 * i),
            site_id="SITE-001",
            node_id="SITE-001-N1",
            cell_id="SITE-001-N1-C1",
            region="North",
            dl_throughput_mbps=float(100 + i * 10),
            prb_util_pct=50.0,
            rrc_setup_success_pct=99.0,
            drop_call_rate_pct=0.5,
            availability_pct=99.9,
        )
        for i in range(4)
    ]
    import asyncio

    asyncio.run(store.insert_many(rows))

    result = asyncio.run(store.query("SITE-001-N1-C1", base, base + timedelta(hours=1), "1h"))
    assert len(result) == 1
    assert result[0]["dlThroughputMbps"] == 115.0


@pytest.mark.asyncio
async def test_batch_writer_stats_and_flush():
    store = MemoryStore()
    writer = BatchWriter(store, max_batch=2, max_wait=1.0)

    raw1 = {
        "sampleId": str(uuid4()),
        "cellId": "C1",
        "timestamp": "2026-10-14T09:15:00Z",
        "kpis": {"dlThroughputMbps": 100.0},
    }
    raw2 = {
        "sampleId": str(uuid4()),
        "cellId": "C1",
        "timestamp": "2026-10-14T09:30:00Z",
        "kpis": {"dlThroughputMbps": 200.0},
    }
    raw3 = {
        "sampleId": str(uuid4()),
        "cellId": "C1",
        "timestamp": "2026-10-14T09:45:00Z",
        "kpis": {"dlThroughputMbps": 300.0},
    }

    await writer.add(raw1)
    await writer.add(raw2)
    await writer.flush()
    stats = writer.stats()
    assert stats["received"] == 2
    assert stats["written"] == 2
    assert stats["invalid"] == 0

    await writer.add(raw3)
    await writer.flush()
    stats = writer.stats()
    assert stats["received"] == 3
    assert stats["written"] == 3

    await writer.flush()
    stats = writer.stats()
    assert stats["written"] == 3


def test_api_healthz():
    with TestClient(app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_api_readyz():
    with TestClient(app) as client:
        resp = client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"
        assert resp.json()["store"] is True
        assert resp.json()["kafka"] is True


def test_api_cells_and_kpis():
    store = MemoryStore()
    base = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
    rows = [
        KpiRow(
            sample_id=uuid4(),
            ts=base + timedelta(minutes=15 * i),
            site_id="SITE-001",
            node_id="SITE-001-N1",
            cell_id="SITE-001-N1-C1",
            region="North",
            dl_throughput_mbps=float(100 + i * 10),
            prb_util_pct=50.0,
            rrc_setup_success_pct=99.0,
            drop_call_rate_pct=0.5,
            availability_pct=99.9,
        )
        for i in range(4)
    ]
    import asyncio

    asyncio.run(store.insert_many(rows))

    import kpi_service.main as main_module

    main_module._store = store

    with TestClient(app) as client:
        resp = client.get("/kpis/cells")
        assert resp.status_code == 200
        cells = resp.json()
        assert len(cells) == 1
        assert cells[0]["cellId"] == "SITE-001-N1-C1"

        resp = client.get("/kpis/cells/SITE-001-N1-C1?agg=1h")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cellId"] == "SITE-001-N1-C1"
        assert data["agg"] == "1h"
        assert len(data["points"]) == 1
        assert data["points"][0]["dlThroughputMbps"] == 115.0


def test_api_invalid_agg():
    with TestClient(app) as client:
        resp = client.get("/kpis/cells/C1?agg=invalid")
        assert resp.status_code == 422


def test_api_from_ge_to():
    with TestClient(app) as client:
        resp = client.get("/kpis/cells/C1?from=2026-10-14T10:00:00Z&to=2026-10-14T09:00:00Z")
        assert resp.status_code == 422


def test_api_range_exceeds_62_days():
    with TestClient(app) as client:
        resp = client.get("/kpis/cells/C1?from=2026-08-01T00:00:00Z&to=2026-10-14T00:00:00Z")
        assert resp.status_code == 422


def test_migration_sql_exists_and_contains_hypertable():
    migration_path = (
        Path(__file__).parent.parent / "src" / "kpi_service" / "migrations" / "001_kpi_samples.sql"
    )
    assert migration_path.exists()
    content = migration_path.read_text()
    assert "create_hypertable" in content
    assert "kpi_samples" in content
    assert "schema_migrations" in content


def test_openapi_contract_paths_match_app() -> None:
    import yaml

    root = Path(__file__).resolve().parents[3]
    contract = yaml.safe_load((root / "contracts/openapi/kpi-service.yaml").read_text())
    app_paths = {
        r.path for r in app.routes if r.path.startswith(("/kpis", "/healthz", "/readyz", "/stats"))
    }
    assert set(contract["paths"]) == {p.replace("{cell_id}", "{cellId}") for p in app_paths}
