"""Tables, migrations and the ticket store (drafts, decisions, hash-chained audit log).

The schema is owned by Alembic (``migrations/``); ``metadata`` mirrors it for queries.
Audit rows are append-only: the store never updates or deletes them, a database trigger
(Postgres and SQLite) rejects UPDATE/DELETE, and each row's ``hash`` chains to the previous
one so ``verify()`` detects edits made around the trigger.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

metadata = sa.MetaData()

tickets = sa.Table(
    "tickets",
    metadata,
    sa.Column("id", sa.String(16), primary_key=True),
    sa.Column("status", sa.String(16), nullable=False),
    sa.Column("title", sa.String(200), nullable=False),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("severity", sa.String(16), nullable=False),
    sa.Column("site_id", sa.String(32)),
    sa.Column("incident_id", sa.String(32)),
    sa.Column("fault_type", sa.String(40)),
    sa.Column("runbook_ids", sa.JSON, nullable=False),
    sa.Column("source_ids", sa.JSON, nullable=False),
    sa.Column("created_by", sa.String(64), nullable=False),
    sa.Column("created_via", sa.String(16), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("decided_by", sa.String(64)),
    sa.Column("decided_at", sa.DateTime(timezone=True)),
    sa.Column("decision_note", sa.Text),
    sa.Column("version", sa.Integer, nullable=False),
)

audit = sa.Table(
    "ticket_audit",
    metadata,
    sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ticket_id", sa.String(16), nullable=False),
    sa.Column("actor", sa.String(64), nullable=False),
    sa.Column("role", sa.String(16), nullable=False),
    sa.Column("action", sa.String(16), nullable=False),
    sa.Column("from_status", sa.String(16)),
    sa.Column("to_status", sa.String(16), nullable=False),
    sa.Column("detail", sa.JSON, nullable=False),
    sa.Column("prev_hash", sa.String(64), nullable=False),
    sa.Column("hash", sa.String(64), nullable=False),
)

GENESIS = "0" * 64
SERVICE_DIR = Path(__file__).resolve().parents[2]


def normalise_url(url: str) -> str:
    """``postgresql://`` -> psycopg 3 driver; anything else is passed through."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def make_engine(url: str) -> Engine:
    url = normalise_url(url)
    if url.startswith("sqlite"):
        kw: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kw["poolclass"] = sa.pool.StaticPool  # one shared in-memory DB
        return sa.create_engine(url, **kw)
    return sa.create_engine(url, pool_pre_ping=True)


def upgrade(engine: Engine) -> None:
    """``alembic upgrade head`` on this engine (startup and tests)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(SERVICE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_DIR / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite drops the zone; values are always written in UTC
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat().replace("+00:00", "Z")


def entry_hash(prev: str, row: dict[str, Any]) -> str:
    body = {k: row[k] for k in ("ts", "ticket_id", "actor", "role", "action")}
    body |= {"from": row["from_status"], "to": row["to_status"], "detail": row["detail"]}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev + canon).encode()).hexdigest()


class Conflict(Exception):
    """The ticket is not a draft any more (already decided, or a stale version)."""


class TicketStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    # --- audit ----------------------------------------------------------------------------
    def _append(self, conn: Connection, **row: Any) -> None:
        if conn.dialect.name == "postgresql":  # serialise writers so the chain stays linear
            conn.execute(sa.text("SELECT pg_advisory_xact_lock(160016)"))
        last = conn.execute(sa.select(audit.c.hash).order_by(audit.c.seq.desc()).limit(1))
        prev = last.scalar() or GENESIS
        row["ts"] = _iso(row["ts"])
        digest = entry_hash(prev, row)
        row["ts"] = datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
        conn.execute(audit.insert().values(**row, prev_hash=prev, hash=digest))

    @staticmethod
    def _audit_out(r: Any) -> dict[str, Any]:
        return {
            "seq": r.seq,
            "ts": _iso(r.ts),
            "ticketId": r.ticket_id,
            "actor": r.actor,
            "role": r.role,
            "action": r.action,
            "fromStatus": r.from_status,
            "toStatus": r.to_status,
            "detail": r.detail,
            "prevHash": r.prev_hash,
            "hash": r.hash,
        }

    def audit_log(self, ticket_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        q = sa.select(audit).order_by(audit.c.seq.desc()).limit(limit)
        if ticket_id:
            q = q.where(audit.c.ticket_id == ticket_id)
        with self.engine.connect() as conn:
            rows = [self._audit_out(r) for r in conn.execute(q)]
        return rows[::-1]

    def verify(self) -> dict[str, Any]:
        prev, n = GENESIS, 0
        with self.engine.connect() as conn:
            for r in conn.execute(sa.select(audit).order_by(audit.c.seq)):
                row = r._asdict()
                row["ts"] = _iso(row["ts"])
                if r.prev_hash != prev or entry_hash(prev, row) != r.hash:
                    return {"ok": False, "entries": n, "brokenAt": r.seq}
                prev, n = r.hash, n + 1
        return {"ok": True, "entries": n, "head": prev}

    # --- tickets --------------------------------------------------------------------------
    @staticmethod
    def _out(r: Any) -> dict[str, Any]:
        return {
            "id": r.id,
            "status": r.status,
            "title": r.title,
            "description": r.description,
            "severity": r.severity,
            "siteId": r.site_id,
            "incidentId": r.incident_id,
            "faultType": r.fault_type,
            "runbookIds": list(r.runbook_ids or []),
            "sourceIds": list(r.source_ids or []),
            "createdBy": r.created_by,
            "createdVia": r.created_via,
            "createdAt": _iso(r.created_at),
            "decidedBy": r.decided_by,
            "decidedAt": _iso(r.decided_at),
            "decisionNote": r.decision_note,
            "version": r.version,
        }

    def create(self, draft: dict[str, Any], actor: str, role: str, via: str) -> dict[str, Any]:
        tid = "TKT-" + secrets.token_hex(5).upper()
        now = _now()
        row = {
            "id": tid,
            "status": "draft",
            "title": draft["title"],
            "description": draft.get("description", ""),
            "severity": draft.get("severity", "major"),
            "site_id": draft.get("siteId"),
            "incident_id": draft.get("incidentId"),
            "fault_type": draft.get("faultType"),
            "runbook_ids": list(draft.get("runbookIds", [])),
            "source_ids": list(draft.get("sourceIds", [])),
            "created_by": actor,
            "created_via": via,
            "created_at": now,
            "version": 1,
        }
        with self.engine.begin() as conn:
            conn.execute(tickets.insert().values(**row))
            detail = {"via": via, "title": row["title"], "severity": row["severity"]}
            if row["incident_id"]:
                detail["incidentId"] = row["incident_id"]
            self._append(
                conn,
                ts=now,
                ticket_id=tid,
                actor=actor,
                role=role,
                action="created",
                from_status=None,
                to_status="draft",
                detail=detail,
            )
        return self.get(tid) or {}

    def get(self, tid: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            r = conn.execute(sa.select(tickets).where(tickets.c.id == tid)).first()
        return self._out(r) if r else None

    def list(
        self, status: str | None = None, incident_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        q = sa.select(tickets).order_by(tickets.c.created_at.desc()).limit(limit)
        if status:
            q = q.where(tickets.c.status == status)
        if incident_id:
            q = q.where(tickets.c.incident_id == incident_id)
        with self.engine.connect() as conn:
            return [self._out(r) for r in conn.execute(q)]

    def decide(
        self,
        tid: str,
        decision: str,
        actor: str,
        role: str,
        note: str,
        version: int | None = None,
    ) -> dict[str, Any] | None:
        to = {"approve": "approved", "reject": "rejected"}[decision]
        now = _now()
        with self.engine.begin() as conn:
            cond = (tickets.c.id == tid) & (tickets.c.status == "draft")
            if version is not None:
                cond &= tickets.c.version == version
            res = conn.execute(
                tickets.update()
                .where(cond)
                .values(
                    status=to,
                    decided_by=actor,
                    decided_at=now,
                    decision_note=note or None,
                    version=tickets.c.version + 1,
                )
            )
            if res.rowcount == 0:
                exists = conn.execute(sa.select(tickets.c.id).where(tickets.c.id == tid)).first()
                if not exists:
                    return None
                raise Conflict(tid)
            self._append(
                conn,
                ts=now,
                ticket_id=tid,
                actor=actor,
                role=role,
                action=to,
                from_status="draft",
                to_status=to,
                detail={"note": note} if note else {},
            )
        return self.get(tid)

    def stats(self) -> dict[str, int]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                sa.select(tickets.c.status, sa.func.count()).group_by(tickets.c.status)
            )
            out = {"draft": 0, "approved": 0, "rejected": 0}
            out.update({s: int(n) for s, n in rows})
        return out
