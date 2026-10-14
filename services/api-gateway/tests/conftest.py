"""Shared test helpers for the gateway (Step 13b user store)."""

from __future__ import annotations

import asyncio

from api_gateway import auth
from api_gateway.users import MemoryUserStore, seed


def use_memory_store(monkeypatch, users: dict[str, tuple[str, str]]) -> MemoryUserStore:
    store = MemoryUserStore()
    asyncio.run(seed(store, users))
    monkeypatch.setattr(auth, "store", store)
    monkeypatch.setattr(auth, "store_state", {"ready": True, "seeded": len(users), "error": None})
    monkeypatch.setattr(auth, "_cache", {})
    return store


import pytest  # noqa: E402


@pytest.fixture
def memory_store_factory(monkeypatch):
    return lambda users: use_memory_store(monkeypatch, users)
