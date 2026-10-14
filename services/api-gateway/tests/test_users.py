"""Step 13b: password policy, hashing and first-run seeding of the user store."""

import asyncio

from api_gateway.users import (
    MemoryUserStore,
    hash_password,
    password_problems,
    seed,
    verify_password,
)


def test_hash_roundtrip_and_no_plaintext():
    h = hash_password("Synthetic-Pass-1!")
    assert h.startswith("$2") and "Synthetic" not in h
    assert verify_password("Synthetic-Pass-1!", h)
    assert not verify_password("nope", h)
    assert not verify_password("x", "not-a-hash")


def test_policy():
    assert password_problems("N3w-Synthetic-pass!") == []
    assert set(password_problems("abc")) >= {"at least 10 characters", "an uppercase letter"}
    assert "must not contain the username" in password_problems("Ajay-Rocks-123!", "ajay")
    # bcrypt 5 raises on >72 bytes; policy must reject before hash_password
    long_pw = "Aa1!" + "x" * 69
    assert "at most 72 bytes" in password_problems(long_pw)
    try:
        hash_password(long_pw)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_seed_only_on_first_run():
    store = MemoryUserStore()
    users = {"viewer": ("viewer", "viewer"), "bad": ("x", "superuser")}
    assert asyncio.run(seed(store, users)) == 1  # invalid role skipped
    assert asyncio.run(seed(store, {"other": ("o", "admin")})) == 0
    assert [u.username for u in asyncio.run(store.list())] == ["viewer"]
    assert store.entries[0]["action"] == "users.seeded"
