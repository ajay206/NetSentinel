"""Startup must survive a DB that is down or rejects the password (no PoolClosed crash)."""

from __future__ import annotations

import asyncio
import time

import pytest
from fastapi.testclient import TestClient
from kpi_service import main as main_module
from kpi_service.main import app
from kpi_service.store import MemoryStore, PgStore

DEAD_DSN = "postgresql://postgres:wrong@127.0.0.1:1/postgres?connect_timeout=1"


def test_pgstore_migrate_retries_with_fresh_pool() -> None:
    store = PgStore(DEAD_DSN, connect_timeout=0.5)

    async def twice() -> None:
        for _ in range(2):
            first = store._pool
            with pytest.raises(Exception) as exc:
                await store.migrate()
            assert type(exc.value).__name__ != "PoolClosed"
            assert store._pool is not first  # replaced, so the next try can open it
        await store.close()

    asyncio.run(twice())


class FlakyStore(MemoryStore):
    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures

    async def migrate(self) -> None:
        if self.failures > 0:
            self.failures -= 1
            raise OSError("db not ready")
        await super().migrate()


def test_app_starts_unready_then_recovers(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "DISABLE_KAFKA", True)
    monkeypatch.setattr(main_module, "_store", FlakyStore(failures=2))
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        for _ in range(100):  # backoff is 1s then 2s
            if client.get("/readyz").status_code == 200:
                break
            time.sleep(0.05)
        assert client.get("/readyz").status_code == 200
    monkeypatch.setattr(main_module, "_store", None)
