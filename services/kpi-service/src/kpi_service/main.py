from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from .consumer import BatchWriter, consume_forever
from .models import AGG_INTERVALS
from .store import MemoryStore, PgStore

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KPI_TOPIC = os.getenv("KPI_TOPIC", "kpis")
DISABLE_KAFKA = os.getenv("DISABLE_KAFKA", "").lower() in ("1", "true", "yes")
KPI_STORE = os.getenv("KPI_STORE", "postgres")

TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "localhost")
TIMESCALE_PORT = os.getenv("TIMESCALE_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{TIMESCALE_HOST}:{TIMESCALE_PORT}/{POSTGRES_DB}",
)

_store: MemoryStore | PgStore | None = None
_consumer_task: asyncio.Task[None] | None = None
_writer: BatchWriter | None = None
_startup_task: asyncio.Task[None] | None = None
_state: dict[str, Any] = {"connected": False}
logger = logging.getLogger("kpi-service")


def get_store() -> MemoryStore | PgStore:
    global _store
    if _store is None:
        raise RuntimeError("Store not initialized")
    return _store


def _build_store() -> MemoryStore | PgStore:
    if KPI_STORE == "memory":
        return MemoryStore()
    return PgStore(DATABASE_URL)


async def _try_migrate(store: MemoryStore | PgStore) -> bool:
    try:
        await store.migrate()
    except Exception as exc:  # DB down, auth failure, ...
        logger.warning("KPI store not ready (%s: %s); will retry", type(exc).__name__, exc)
        return False
    _state["migrated"] = True
    return True


def _start_consumer() -> None:
    global _consumer_task
    if not DISABLE_KAFKA and _store is not None and _writer is not None:
        _consumer_task = asyncio.create_task(
            consume_forever(_store, _writer, KAFKA_BOOTSTRAP, KPI_TOPIC, _state)
        )


async def _migrate_with_backoff(store: MemoryStore | PgStore, max_delay: float = 30.0) -> None:
    delay = 1.0
    while not await _try_migrate(store):
        await asyncio.sleep(delay)
        delay = min(delay * 2, max_delay)
    logger.info("KPI store ready")
    _start_consumer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store, _consumer_task, _writer, _state, _startup_task
    if _store is None:
        _store = _build_store()
    _writer = BatchWriter(_store)

    # Never crash on a slow or misconfigured DB: try once now, then keep retrying with
    # backoff in the background. /readyz stays 503 until migrations are done.
    _state["migrated"] = False
    if not await _try_migrate(_store):
        _startup_task = asyncio.create_task(_migrate_with_backoff(_store))
    else:
        _start_consumer()

    yield

    if _startup_task:
        _startup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _startup_task
        _startup_task = None
    if _consumer_task:
        _consumer_task.cancel()
        try:
            await _consumer_task
        except asyncio.CancelledError:
            pass
    if isinstance(_store, PgStore):
        await _store.close()


app = FastAPI(title="KPI Service", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> JSONResponse:
    store_ok = bool(_state.get("migrated")) and (await _store.ping() if _store else False)
    kafka_ok = DISABLE_KAFKA or _state.get("connected", False)
    status = "ready" if store_ok and kafka_ok else "not ready"
    code = 200 if store_ok and kafka_ok else 503
    return JSONResponse(
        status_code=code,
        content={"status": status, "store": store_ok, "kafka": bool(kafka_ok)},
    )


@app.get("/stats")
async def stats() -> dict[str, int]:
    if _writer is None:
        return {"received": 0, "written": 0, "invalid": 0}
    return dict(_writer.stats())


@app.get("/kpis/cells")
async def list_cells(limit: int = Query(500, ge=1, le=5000)) -> list[dict[str, Any]]:
    store = get_store()
    cells = await store.cells(limit)
    return cells


@app.get("/kpis/cells/{cell_id}")
async def get_cell_kpis(
    cell_id: str,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    agg: str = Query("1h"),
) -> dict[str, Any]:
    if agg not in AGG_INTERVALS:
        raise HTTPException(status_code=422, detail=f"Invalid agg: {agg}")

    store = get_store()
    cell_info = await store.cell_info(cell_id)

    now = datetime.now(UTC)
    if to:
        try:
            to_dt = datetime.fromisoformat(to.replace("Z", "+00:00"))
            if to_dt.tzinfo is None:
                to_dt = to_dt.replace(tzinfo=UTC)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid 'to' timestamp") from exc
    else:
        to_dt = cell_info["lastTs"] if cell_info else now
        if isinstance(to_dt, str):
            to_dt = datetime.fromisoformat(to_dt.replace("Z", "+00:00"))
            # make the newest sample part of the default (end-exclusive) window
            to_dt += timedelta(seconds=1)

    if from_:
        try:
            from_dt = datetime.fromisoformat(from_.replace("Z", "+00:00"))
            if from_dt.tzinfo is None:
                from_dt = from_dt.replace(tzinfo=UTC)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid 'from' timestamp") from exc
    else:
        from_dt = to_dt - timedelta(days=1)

    if from_dt >= to_dt:
        raise HTTPException(status_code=422, detail="'from' must be before 'to'")

    if to_dt - from_dt > timedelta(days=62):
        raise HTTPException(status_code=422, detail="Range exceeds 62 days")

    points = await store.query(cell_id, from_dt, to_dt, agg)
    return {
        "cellId": cell_id,
        "agg": agg,
        "from": from_dt.isoformat().replace("+00:00", "Z"),
        "to": to_dt.isoformat().replace("+00:00", "Z"),
        "points": points,
    }


def run() -> None:
    import uvicorn

    port = int(os.getenv("PORT", "8002"))
    uvicorn.run("kpi_service.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
