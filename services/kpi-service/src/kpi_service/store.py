from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .models import AGG_INTERVALS, KpiRow


class MemoryStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, datetime], KpiRow] = {}
        self._lock = asyncio.Lock()

    async def migrate(self) -> None:
        return

    async def insert_many(self, rows: Sequence[KpiRow]) -> int:
        async with self._lock:
            count = 0
            for row in rows:
                key = (row.cell_id, row.ts)
                if key not in self._rows:
                    self._rows[key] = row
                    count += 1
            return count

    async def query(
        self,
        cell_id: str,
        start: datetime,
        end: datetime,
        agg: str,
    ) -> list[dict[str, Any]]:
        async with self._lock:
            filtered = [
                row
                for row in self._rows.values()
                if row.cell_id == cell_id and start <= row.ts < end
            ]
            filtered.sort(key=lambda r: r.ts)

            if agg == "raw":
                return [_row_to_dict(row) for row in filtered]

            bucket_seconds = _agg_to_seconds(agg)
            if bucket_seconds is None:
                return []

            buckets: dict[datetime, list[KpiRow]] = {}
            for row in filtered:
                bucket_ts = _floor_to_bucket(row.ts, bucket_seconds)
                buckets.setdefault(bucket_ts, []).append(row)

            result = []
            for bucket_ts in sorted(buckets.keys()):
                rows_in_bucket = buckets[bucket_ts]
                avg_row = _average_rows(rows_in_bucket, bucket_ts)
                result.append(_row_to_dict(avg_row))
            return result

    async def cells(self, limit: int = 500) -> list[dict[str, Any]]:
        async with self._lock:
            cell_info: dict[str, dict[str, Any]] = {}
            for row in self._rows.values():
                info = cell_info.get(row.cell_id)
                if info is None:
                    cell_info[row.cell_id] = {
                        "cellId": row.cell_id,
                        "siteId": row.site_id,
                        "region": row.region,
                        "lastTs": row.ts,
                        "sampleCount": 1,
                    }
                else:
                    info["sampleCount"] += 1
                    if row.ts > info["lastTs"]:
                        info["lastTs"] = row.ts

            result = sorted(cell_info.values(), key=lambda x: x["lastTs"], reverse=True)
            for info in result:
                info["lastTs"] = info["lastTs"].isoformat().replace("+00:00", "Z")
            return result[:limit]

    async def cell_info(self, cell_id: str) -> dict[str, Any] | None:
        cells = await self.cells(limit=len(self._rows) or 1)
        return next((c for c in cells if c["cellId"] == cell_id), None)

    async def ping(self) -> bool:
        return True


class PgStore:
    def __init__(self, dsn: str) -> None:
        self._pool = AsyncConnectionPool(
            dsn,
            min_size=1,
            max_size=4,
            open=False,
            kwargs={"row_factory": dict_row},
        )

    async def migrate(self) -> None:
        await self._pool.open()
        await self._pool.wait()
        migrations_dir = Path(__file__).parent / "migrations"
        sql_files = sorted(migrations_dir.glob("*.sql"))
        async with self._pool.connection() as conn:
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            for sql_file in sql_files:
                version = sql_file.stem
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT 1 FROM schema_migrations WHERE version = %s",
                        (version,),
                    )
                    if await cur.fetchone():
                        continue
                    sql = sql_file.read_text()
                    await cur.execute(sql)
                    await cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (version,),
                    )
            await conn.commit()

    async def insert_many(self, rows: Sequence[KpiRow]) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO kpi_samples (
                sample_id, ts, site_id, node_id, cell_id, region,
                dl_throughput_mbps, prb_util_pct, rrc_setup_success_pct,
                drop_call_rate_pct, availability_pct
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (cell_id, ts) DO NOTHING
        """
        params = [
            (
                str(row.sample_id),
                row.ts,
                row.site_id,
                row.node_id,
                row.cell_id,
                row.region,
                row.dl_throughput_mbps,
                row.prb_util_pct,
                row.rrc_setup_success_pct,
                row.drop_call_rate_pct,
                row.availability_pct,
            )
            for row in rows
        ]
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(sql, params)
                await conn.commit()
                return cur.rowcount or 0

    async def query(
        self,
        cell_id: str,
        start: datetime,
        end: datetime,
        agg: str,
    ) -> list[dict[str, Any]]:
        if agg == "raw":
            sql = """
                SELECT
                    ts,
                    dl_throughput_mbps,
                    prb_util_pct,
                    rrc_setup_success_pct,
                    drop_call_rate_pct,
                    availability_pct
                FROM kpi_samples
                WHERE cell_id = %s AND ts >= %s AND ts < %s
                ORDER BY ts ASC
            """
            params = (cell_id, start, end)
        else:
            interval = AGG_INTERVALS.get(agg)
            if interval is None:
                return []
            sql = """
                SELECT
                    time_bucket(%s::interval, ts) AS bucket_ts,
                    AVG(dl_throughput_mbps) AS dl_throughput_mbps,
                    AVG(prb_util_pct) AS prb_util_pct,
                    AVG(rrc_setup_success_pct) AS rrc_setup_success_pct,
                    AVG(drop_call_rate_pct) AS drop_call_rate_pct,
                    AVG(availability_pct) AS availability_pct
                FROM kpi_samples
                WHERE cell_id = %s AND ts >= %s AND ts < %s
                GROUP BY bucket_ts
                ORDER BY bucket_ts ASC
            """
            params = (interval, cell_id, start, end)

        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()

        result = []
        for row in rows:
            ts = row["bucket_ts"] if agg != "raw" else row["ts"]
            result.append(
                {
                    "ts": ts.isoformat().replace("+00:00", "Z"),
                    "dlThroughputMbps": row.get("dl_throughput_mbps"),
                    "prbUtilPct": row.get("prb_util_pct"),
                    "rrcSetupSuccessPct": row.get("rrc_setup_success_pct"),
                    "dropCallRatePct": row.get("drop_call_rate_pct"),
                    "availabilityPct": row.get("availability_pct"),
                }
            )
        return result

    async def cells(self, limit: int = 500) -> list[dict[str, Any]]:
        sql = """
            SELECT
                cell_id,
                site_id,
                region,
                MAX(ts) AS last_ts,
                COUNT(*) AS sample_count
            FROM kpi_samples
            GROUP BY cell_id, site_id, region
            ORDER BY last_ts DESC
            LIMIT %s
        """
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (limit,))
                rows = await cur.fetchall()

        return [
            {
                "cellId": row["cell_id"],
                "siteId": row["site_id"],
                "region": row["region"],
                "lastTs": row["last_ts"].isoformat().replace("+00:00", "Z"),
                "sampleCount": row["sample_count"],
            }
            for row in rows
        ]

    async def cell_info(self, cell_id: str) -> dict[str, Any] | None:
        sql = (
            "SELECT max(ts) AS last_ts, count(*) AS sample_count FROM kpi_samples"
            " WHERE cell_id = %s"
        )
        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (cell_id,))
                row = await cur.fetchone()
        if not row or row["last_ts"] is None:
            return None
        return {
            "cellId": cell_id,
            "lastTs": row["last_ts"].isoformat().replace("+00:00", "Z"),
            "sampleCount": row["sample_count"],
        }

    async def ping(self) -> bool:
        try:
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._pool.close()


def _agg_to_seconds(agg: str) -> int | None:
    mapping = {"15m": 900, "1h": 3600, "1d": 86400}
    return mapping.get(agg)


def _floor_to_bucket(dt: datetime, bucket_seconds: int) -> datetime:
    epoch = dt.timestamp()
    floored = math.floor(epoch / bucket_seconds) * bucket_seconds
    return datetime.fromtimestamp(floored, tz=UTC)


def _average_rows(rows: Sequence[KpiRow], bucket_ts: datetime) -> KpiRow:
    first = rows[0]
    kpi_fields = [
        "dl_throughput_mbps",
        "prb_util_pct",
        "rrc_setup_success_pct",
        "drop_call_rate_pct",
        "availability_pct",
    ]
    averages = {}
    for field in kpi_fields:
        values = [getattr(r, field) for r in rows if getattr(r, field) is not None]
        averages[field] = sum(values) / len(values) if values else None

    return KpiRow(
        sample_id=first.sample_id,
        ts=bucket_ts,
        site_id=first.site_id,
        node_id=first.node_id,
        cell_id=first.cell_id,
        region=first.region,
        **averages,
    )


def _row_to_dict(row: KpiRow) -> dict[str, Any]:
    return {
        "ts": row.ts.isoformat().replace("+00:00", "Z"),
        "dlThroughputMbps": row.dl_throughput_mbps,
        "prbUtilPct": row.prb_util_pct,
        "rrcSetupSuccessPct": row.rrc_setup_success_pct,
        "dropCallRatePct": row.drop_call_rate_pct,
        "availabilityPct": row.availability_pct,
    }
