"""Step 13b: persisted users (bcrypt), lockout, token versions and the audit log.

Two stores share one async interface: ``PgUserStore`` (TimescaleDB/Postgres tables ``ns_users``
and ``audit_log``) for compose, and ``MemoryUserStore`` for tests and DB-less dev. Demo users
(password = username) are seeded on first run only when the user table is empty. Synthetic
data only; hashes and passwords are never logged.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

import bcrypt

logger = logging.getLogger(__name__)

ROLES = ("viewer", "operator", "admin")
USERNAME_RE = re.compile(r"^[a-z][a-z0-9._-]{2,31}$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def password_problems(password: str, username: str = "") -> list[str]:
    """Strength policy shared with the console (lib/passwordPolicy.ts)."""
    problems = []
    if len(password) < 10:
        problems.append("at least 10 characters")
    if len(password) > 128:
        problems.append("at most 128 characters")
    if not re.search(r"[a-z]", password):
        problems.append("a lowercase letter")
    if not re.search(r"[A-Z]", password):
        problems.append("an uppercase letter")
    if not re.search(r"\d", password):
        problems.append("a digit")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("a symbol")
    if username and username.lower() in password.lower():
        problems.append("must not contain the username")
    return problems


@dataclass
class User:
    username: str
    role: str
    password_hash: str = field(repr=False)
    disabled: bool = False
    failed_logins: int = 0
    locked_until: float = 0.0
    token_version: int = 1
    created_at: float = field(default_factory=time.time)
    password_changed_at: float | None = None

    def public(self, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        return {
            "username": self.username,
            "role": self.role,
            "disabled": self.disabled,
            "locked": self.locked_until > now,
            "failedLogins": self.failed_logins,
            "createdAt": self.created_at,
            "passwordChangedAt": self.password_changed_at,
        }


class UserStore(Protocol):
    kind: str

    async def start(self) -> None: ...
    async def get(self, username: str) -> User | None: ...
    async def list(self) -> list[User]: ...
    async def create(self, user: User) -> bool: ...
    async def save(self, user: User) -> None: ...
    async def audit(self, actor: str, action: str, target: str, detail: dict[str, Any]) -> None: ...
    async def audit_log(self, limit: int = 200) -> list[dict[str, Any]]: ...


class MemoryUserStore:
    kind = "memory"

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.entries: list[dict[str, Any]] = []

    async def start(self) -> None:
        return None

    async def get(self, username: str) -> User | None:
        return self.users.get(username)

    async def list(self) -> list[User]:
        return sorted(self.users.values(), key=lambda u: u.username)

    async def create(self, user: User) -> bool:
        if user.username in self.users:
            return False
        self.users[user.username] = user
        return True

    async def save(self, user: User) -> None:
        self.users[user.username] = user

    async def audit(self, actor: str, action: str, target: str, detail: dict[str, Any]) -> None:
        self.entries.append(
            {
                "id": len(self.entries) + 1,
                "ts": time.time(),
                "actor": actor,
                "action": action,
                "target": target,
                "detail": detail,
            }
        )

    async def audit_log(self, limit: int = 200) -> list[dict[str, Any]]:
        return list(reversed(self.entries))[:limit]


SCHEMA = """
CREATE TABLE IF NOT EXISTS ns_users (
    username TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('viewer', 'operator', 'admin')),
    password_hash TEXT NOT NULL,
    disabled BOOLEAN NOT NULL DEFAULT FALSE,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until DOUBLE PRECISION NOT NULL DEFAULT 0,
    token_version INTEGER NOT NULL DEFAULT 1,
    created_at DOUBLE PRECISION NOT NULL,
    password_changed_at DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    ts DOUBLE PRECISION NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS audit_log_ts_idx ON audit_log (ts DESC);
"""

_COLS = (
    "username, role, password_hash, disabled, failed_logins, locked_until, token_version, "
    "created_at, password_changed_at"
)


class PgUserStore:
    """Postgres-backed store (psycopg 3 async pool). Tables are created on start."""

    kind = "postgres"

    def __init__(self, conninfo: str) -> None:
        from psycopg_pool import AsyncConnectionPool

        self.pool = AsyncConnectionPool(conninfo, min_size=1, max_size=4, open=False)

    async def start(self) -> None:
        await self.pool.open(wait=True, timeout=30)
        async with self.pool.connection() as conn:
            await conn.execute(SCHEMA)

    async def get(self, username: str) -> User | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                f"SELECT {_COLS} FROM ns_users WHERE username = %s", (username,)
            )
            row = await cur.fetchone()
        return User(*row) if row else None

    async def list(self) -> list[User]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(f"SELECT {_COLS} FROM ns_users ORDER BY username")
            rows = await cur.fetchall()
        return [User(*r) for r in rows]

    async def create(self, user: User) -> bool:
        d = asdict(user)
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                f"INSERT INTO ns_users ({_COLS}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (username) DO NOTHING",
                tuple(d.values()),
            )
            return cur.rowcount == 1

    async def save(self, user: User) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE ns_users SET role=%s, password_hash=%s, disabled=%s, failed_logins=%s, "
                "locked_until=%s, token_version=%s, password_changed_at=%s WHERE username=%s",
                (
                    user.role,
                    user.password_hash,
                    user.disabled,
                    user.failed_logins,
                    user.locked_until,
                    user.token_version,
                    user.password_changed_at,
                    user.username,
                ),
            )

    async def audit(self, actor: str, action: str, target: str, detail: dict[str, Any]) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO audit_log (ts, actor, action, target, detail) "
                "VALUES (%s,%s,%s,%s,%s::jsonb)",
                (time.time(), actor, action, target, json.dumps(detail)),
            )

    async def audit_log(self, limit: int = 200) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id, ts, actor, action, target, detail FROM audit_log "
                "ORDER BY ts DESC, id DESC LIMIT %s",
                (limit,),
            )
            rows = await cur.fetchall()
        keys = ("id", "ts", "actor", "action", "target", "detail")
        return [dict(zip(keys, r, strict=True)) for r in rows]


async def seed(store: UserStore, seed_users: dict[str, tuple[str, str]]) -> int:
    """Insert seed users only when the table is empty (first run). Returns the count added."""
    if await store.list():
        return 0
    added = 0
    for username, (password, role) in seed_users.items():
        if role in ROLES and await store.create(
            User(username=username, role=role, password_hash=hash_password(password))
        ):
            added += 1
    if added:
        await store.audit("system", "users.seeded", "*", {"count": added})
    return added
