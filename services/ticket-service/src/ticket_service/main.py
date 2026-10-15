"""W16 ticket-service: drafts, human approval (draft -> approved | rejected), audit log.

Reached only through the gateway, which authenticates the user and forwards
``X-NS-User`` / ``X-NS-Role`` / ``X-NS-Via``. The service re-checks roles (defence in depth):
operators, admins and the internal service principal (MCP) may draft; only operators and
admins may decide. With ``TICKET_SERVICE_TOKEN`` set, callers must also send
``X-NS-Internal-Token`` (the gateway does), so the headers cannot be forged from outside.
"""

from __future__ import annotations

import hmac
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .db import Conflict, TicketStore, make_engine, upgrade

logger = logging.getLogger("ticket_service")

DRAFT_ROLES = {"operator", "admin", "service"}
DECIDE_ROLES = {"operator", "admin"}
TICKET_ID_RE = re.compile(r"^TKT-[0-9A-F]{10}$")
ID_RE = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"
Severity = Literal["critical", "major", "minor", "warning"]


class DraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=4000)
    severity: Severity = "major"
    siteId: str | None = Field(default=None, pattern=r"^SITE-\d{3}$")
    incidentId: str | None = Field(default=None, pattern=r"^INC-[0-9A-F]{10}$")
    faultType: str | None = Field(default=None, pattern=r"^[a-z_]{2,40}$")
    runbookIds: list[str] = Field(default_factory=list, max_length=10)
    sourceIds: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("runbookIds")
    @classmethod
    def _runbooks(cls, v: list[str]) -> list[str]:
        for rid in v:
            if not re.fullmatch(r"RB-[A-Z]{3}-\d{3}", rid):
                raise ValueError(f"bad runbook id {rid!r}")
        return v

    @field_validator("sourceIds")
    @classmethod
    def _sources(cls, v: list[str]) -> list[str]:
        for sid in v:
            if not re.fullmatch(ID_RE, sid):
                raise ValueError(f"bad source id {sid!r}")
        return v


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(default="", max_length=500)
    version: int | None = Field(default=None, ge=1)


def _caller(user: str | None, role: str | None, token: str | None) -> tuple[str, str]:
    expected = os.getenv("TICKET_SERVICE_TOKEN")
    if expected and not hmac.compare_digest((token or "").encode(), expected.encode()):
        raise HTTPException(401, "missing or invalid internal token")
    if not user or not role or not re.fullmatch(ID_RE, user):
        raise HTTPException(401, "missing caller identity (call through the gateway)")
    return user, role


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = make_engine(os.getenv("DATABASE_URL", "sqlite:///./tickets.db"))
    if os.getenv("TICKET_AUTO_MIGRATE", "1") == "1":
        upgrade(engine)
    app.state.store = TicketStore(engine)
    yield
    engine.dispose()


app = FastAPI(title="ticket-service", version="0.1.0", lifespan=lifespan)

User = Annotated[str | None, Header(alias="X-NS-User")]
Role = Annotated[str | None, Header(alias="X-NS-Role")]
Token = Annotated[str | None, Header(alias="X-NS-Internal-Token")]


def _store(request: Request) -> TicketStore:
    return request.app.state.store


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz(request: Request) -> JSONResponse:
    try:
        _store(request).stats()
    except Exception as exc:  # noqa: BLE001 - report any DB failure as not ready
        return JSONResponse({"error": type(exc).__name__}, status_code=503)
    return JSONResponse({"status": "ready"})


@app.post("/tickets/drafts", status_code=201)
def create_draft(
    body: DraftIn,
    request: Request,
    x_user: User = None,
    x_role: Role = None,
    x_token: Token = None,
    x_via: Annotated[str | None, Header(alias="X-NS-Via")] = None,
) -> dict[str, Any]:
    user, role = _caller(x_user, x_role, x_token)
    if role not in DRAFT_ROLES:
        raise HTTPException(403, "drafting tickets needs the operator role")
    via = "mcp" if role == "service" else (x_via if x_via in ("ui", "api") else "api")
    if role == "service":
        user = f"service:{x_via or 'mcp'}"[:64]
    return _store(request).create(body.model_dump(), user, role, via)


@app.get("/tickets")
def list_tickets(
    request: Request,
    status: Literal["draft", "approved", "rejected"] | None = None,
    incidentId: Annotated[str | None, Query(pattern=r"^INC-[0-9A-F]{10}$")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    store = _store(request)
    return {"items": store.list(status, incidentId, limit), "counts": store.stats()}


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, request: Request) -> dict[str, Any]:
    t = _store(request).get(ticket_id) if TICKET_ID_RE.match(ticket_id) else None
    if t is None:
        raise HTTPException(404, "ticket not found")
    return t


@app.get("/tickets/{ticket_id}/audit")
def ticket_audit(ticket_id: str, request: Request) -> dict[str, Any]:
    store = _store(request)
    if not TICKET_ID_RE.match(ticket_id) or store.get(ticket_id) is None:
        raise HTTPException(404, "ticket not found")
    return {"ticketId": ticket_id, "entries": store.audit_log(ticket_id)}


@app.post("/tickets/{ticket_id}/{decision}")
def decide(
    ticket_id: str,
    decision: str,
    body: DecisionIn,
    request: Request,
    x_user: User = None,
    x_role: Role = None,
    x_token: Token = None,
) -> dict[str, Any]:
    if decision not in ("approve", "reject") or not TICKET_ID_RE.match(ticket_id):
        raise HTTPException(404, "not found")
    user, role = _caller(x_user, x_role, x_token)
    if role not in DECIDE_ROLES:
        raise HTTPException(403, "only operators may approve or reject tickets")
    if decision == "reject" and not body.note.strip():
        raise HTTPException(422, "rejecting needs a note")
    try:
        t = _store(request).decide(ticket_id, decision, user, role, body.note.strip(), body.version)
    except Conflict as exc:
        raise HTTPException(409, "ticket is not a draft (already decided or stale)") from exc
    if t is None:
        raise HTTPException(404, "ticket not found")
    return t


@app.get("/audit")
def audit_log(
    request: Request, limit: Annotated[int, Query(ge=1, le=1000)] = 200
) -> dict[str, Any]:
    return {"entries": _store(request).audit_log(limit=limit)}


@app.get("/audit/verify")
def audit_verify(request: Request) -> dict[str, Any]:
    return _store(request).verify()
