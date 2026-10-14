"""W11 + Step 13b: JWT login, RBAC (viewer < operator < admin) and rate limits for the gateway.

HS256 tokens are issued by ``POST /api/auth/login`` against a persisted user table (bcrypt
hashes in Postgres, see ``users.py``; demo users are seeded on first run; synthetic data only).
Tokens carry a ``tv`` (token version) claim; changing or resetting a password, changing a role
or disabling a user bumps the version, so older tokens stop working at once. Repeated failed
logins lock the account for a while. ``AuthMiddleware`` is pure ASGI so it also guards
WebSockets, where browsers cannot set headers and pass ``?token=`` instead. See ADR-014.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs

import jwt
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from starlette.types import ASGIApp, Receive, Scope, Send

from api_gateway.users import (
    ROLES,
    USERNAME_RE,
    MemoryUserStore,
    PgUserStore,
    User,
    UserStore,
    hash_password,
    password_problems,
    seed,
    verify_password,
)

logger = logging.getLogger(__name__)


def role_at_least(role: str, needed: str) -> bool:
    try:
        return ROLES.index(role) >= ROLES.index(needed)
    except ValueError:
        return False


@dataclass
class AuthSettings:
    disabled: bool
    secret: str
    ttl_seconds: int
    users: dict[str, tuple[str, str]]
    rate_per_min: int
    login_rate_per_min: int
    service_token: str | None = field(default=None, repr=False)
    lockout_threshold: int = 5
    lockout_seconds: int = 900
    user_store: str = "memory"
    database_url: str = field(default="", repr=False)

    @staticmethod
    def _parse_users(s: str) -> dict[str, tuple[str, str]]:
        out: dict[str, tuple[str, str]] = {}
        for entry in filter(None, s.split(",")):
            parts = entry.split(":")
            if len(parts) != 3:
                continue
            username, password, role = parts
            if role not in ROLES:
                continue
            out[username] = (password, role)
        return out

    @classmethod
    def from_env(cls) -> AuthSettings:
        disabled = os.getenv("AUTH_DISABLED") == "1"
        secret = os.getenv("JWT_SECRET")
        if not secret:
            secret = secrets.token_urlsafe(32)
            logger.warning("JWT_SECRET not set; using a random per-process secret")
        elif len(secret) < 32:
            logger.warning("JWT_SECRET is shorter than 32 characters; use a longer one")
        ttl_seconds = int(os.getenv("JWT_TTL_SECONDS", "28800"))
        users_raw = os.getenv("GATEWAY_USERS", "")
        users = cls._parse_users(users_raw)

        if not users and os.getenv("DEMO_USERS", "1") != "0":
            users = {
                "viewer": ("viewer", "viewer"),
                "operator": ("operator", "operator"),
                "admin": ("admin", "admin"),
            }
            logger.warning("DEMO_USERS active (password = username); local synthetic demo only")

        rate_per_min = int(os.getenv("RATE_LIMIT_PER_MIN", "600"))
        login_rate_per_min = int(os.getenv("LOGIN_RATE_PER_MIN", "10"))
        return cls(
            disabled=disabled,
            secret=secret,
            ttl_seconds=ttl_seconds,
            users=users,
            rate_per_min=rate_per_min,
            login_rate_per_min=login_rate_per_min,
            service_token=os.getenv("GATEWAY_SERVICE_TOKEN") or None,
            lockout_threshold=int(os.getenv("LOGIN_MAX_FAILURES", "5")),
            lockout_seconds=int(os.getenv("LOCKOUT_SECONDS", "900")),
            user_store=os.getenv("USER_STORE", "memory"),
            database_url=_database_url(),
        )


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "postgres")
    pw = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("TIMESCALE_HOST", "localhost")
    port = os.getenv("TIMESCALE_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "postgres")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


settings = AuthSettings.from_env()
store: UserStore = MemoryUserStore()
store_state: dict[str, Any] = {"ready": False, "seeded": 0, "error": None}
_cache: dict[str, tuple[float, User | None]] = {}
_CACHE_TTL = 2.0


async def init_store(retries: int = 30, delay: float = 2.0) -> None:
    """Open the configured user store and seed it on first run (retries while Postgres starts)."""
    global store
    if settings.user_store == "postgres":
        store = PgUserStore(settings.database_url)
    for attempt in range(1, retries + 1):
        try:
            await store.start()
            store_state["seeded"] = await seed(store, settings.users)
            store_state.update(ready=True, error=None)
            logger.info("user store %s ready (%d seeded)", store.kind, store_state["seeded"])
            return
        except Exception as exc:  # noqa: BLE001 - keep retrying, report the type only
            store_state["error"] = type(exc).__name__
            logger.warning("user store not ready (attempt %d): %s", attempt, type(exc).__name__)
            await asyncio.sleep(delay)


async def get_user(username: str, fresh: bool = False) -> User | None:
    now = time.monotonic()
    hit = _cache.get(username)
    if not fresh and hit and hit[0] > now:
        return hit[1]
    user = await store.get(username)
    _cache[username] = (now + _CACHE_TTL, user)
    return user


async def save_user(user: User) -> None:
    await store.save(user)
    _cache.pop(user.username, None)


class AuthError(HTTPException):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)


def issue_token(username: str, role: str, now: float | None = None, token_version: int = 1) -> str:
    now = time.time() if now is None else now
    payload = {
        "sub": username,
        "role": role,
        "tv": token_version,
        "iat": int(now),
        "exp": int(now + settings.ttl_seconds),
        "iss": "netsentinel-gateway",
    }
    return jwt.encode(payload, settings.secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret,
            algorithms=["HS256"],
            issuer="netsentinel-gateway",
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc

    role = payload.get("role")
    if role not in ROLES:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid role in token")
    return payload


_DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")


async def authenticate(username: str, password: str, now: float | None = None) -> User:
    """Check credentials with lockout: 401 bad credentials, 403 disabled, 423 locked."""
    now = time.time() if now is None else now
    user = await get_user(username, fresh=True)
    if user is None:
        verify_password(password, _DUMMY_HASH)  # same cost as a real check
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if user.locked_until > now:
        raise AuthError(status.HTTP_423_LOCKED, "Account locked; try later or ask an admin")
    if not verify_password(password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= settings.lockout_threshold:
            user.locked_until = now + settings.lockout_seconds
            user.failed_logins = 0
            await save_user(user)
            await store.audit(
                "system", "user.locked", username, {"afterFailures": settings.lockout_threshold}
            )
            raise AuthError(status.HTTP_423_LOCKED, "Account locked; try later or ask an admin")
        await save_user(user)
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if user.disabled:
        raise AuthError(status.HTTP_403_FORBIDDEN, "Account disabled")
    if user.failed_logins or user.locked_until:
        user.failed_logins = 0
        user.locked_until = 0.0
        await save_user(user)
    return user


def required_role(method: str, path: str) -> str | None:
    if method == "OPTIONS" or path in (
        "/health",
        "/healthz",
        "/readyz",
        "/api/auth/login",
        "/docs",
        "/openapi.json",
    ):
        return None
    if method == "POST" and path == "/api/copilot/analyze":
        return "operator"
    if path.startswith("/api/auth/users") or path.startswith("/api/admin"):
        return "admin"
    # Step 13b: incident and alarm workflow actions (ack / assign / resolve with notes)
    if method == "POST" and _ACTION_RE.match(path):
        return "operator"
    if path.startswith("/api") or path.startswith("/ws"):
        return "viewer"
    return None


_ACTION_RE = re.compile(r"^/api/(incidents/[^/]+|alarms)/actions$")


class RateLimiter:
    _max_keys = 10000

    def __init__(self) -> None:
        self._data: dict[str, deque[float]] = {}
        self._order: deque[str] = deque()

    def hit(self, key: str, limit: int, now: float | None = None) -> float | None:
        now = time.time() if now is None else now
        dq = self._data.get(key)
        if dq is None:
            if len(self._order) >= self._max_keys:
                oldest = self._order.popleft()
                self._data.pop(oldest, None)
            dq = deque()
            self._data[key] = dq
            self._order.append(key)
        # prune old timestamps
        cutoff = now - 60
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            retry = dq[0] + 60 - now
            return max(retry, 0.0)
        dq.append(now)
        return None


limiter = RateLimiter()
login_limiter = RateLimiter()


def _service_principal(token: str) -> dict[str, str] | None:
    """Internal callers (copilot, mcp-server) use a static token with the viewer role."""
    svc = settings.service_token
    if svc and hmac.compare_digest(token.encode(), svc.encode()):
        return {"username": "service", "role": "viewer"}
    return None


class AuthMiddleware:
    """Pure ASGI: guards HTTP and WebSocket scopes; lifespan passes through."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or settings.disabled:
            await self.app(scope, receive, send)
            return
        is_ws = scope["type"] == "websocket"
        method = "GET" if is_ws else scope["method"]
        path = scope["path"]
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        if path == "/api/auth/login" and method == "POST":
            retry = login_limiter.hit(client_ip, settings.login_rate_per_min)
            if retry is not None:
                await _deny(send, 429, "Too many login attempts", {"Retry-After": _secs(retry)})
                return
            await self.app(scope, receive, send)
            return

        needed = required_role(method, path)
        if needed is None:
            await self.app(scope, receive, send)
            return

        token = _token_from(scope, is_ws)
        if not token:
            await _reject(send, is_ws, 401, "Missing bearer token")
            return
        user = _service_principal(token)
        if user is None:
            try:
                claims = decode_token(token)
            except AuthError as exc:
                await _reject(send, is_ws, 401, str(exc.detail))
                return
            if not store_state["ready"]:
                await _reject(send, is_ws, 503, "User store not ready")
                return
            try:
                account = await get_user(str(claims["sub"]))
            except Exception as exc:  # noqa: BLE001 - DB hiccup: fail closed, no stack to client
                logger.warning("user lookup failed: %s", type(exc).__name__)
                await _reject(send, is_ws, 503, "User store unavailable")
                return
            if (
                account is None
                or account.disabled
                or int(claims.get("tv", 0)) != account.token_version
            ):
                await _reject(send, is_ws, 401, "Token revoked; sign in again")
                return
            # the live role wins: a demotion takes effect without waiting for token expiry
            user = {"username": account.username, "role": account.role}

        if not role_at_least(user["role"], needed):
            await _reject(send, is_ws, 403, f"Requires role {needed}")
            return

        retry = limiter.hit(user["username"], settings.rate_per_min)
        if retry is not None:
            await _reject(send, is_ws, 429, "Rate limit exceeded", {"Retry-After": _secs(retry)})
            return

        scope.setdefault("state", {})["user"] = user
        await self.app(scope, receive, send)


def _secs(retry: float) -> str:
    return str(max(1, int(retry + 0.999)))


def _token_from(scope: Scope, is_ws: bool) -> str | None:
    if is_ws:
        qs = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        values = qs.get("token")
        return values[0] if values else None
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            text = value.decode("latin-1")
            if text[:7].lower() == "bearer ":
                return text[7:].strip() or None
    return None


async def _deny(send: Send, code: int, detail: str, headers: dict[str, str] | None = None) -> None:
    body = json.dumps({"detail": detail}).encode()
    raw = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    raw += [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    await send({"type": "http.response.start", "status": code, "headers": raw})
    await send({"type": "http.response.body", "body": body})


async def _reject(
    send: Send, is_ws: bool, code: int, detail: str, headers: dict[str, str] | None = None
) -> None:
    if is_ws:
        # 4401 / 4403 / 4429 mirror the HTTP status for the browser's close handler
        await send({"type": "websocket.close", "code": 4000 + code})
        return
    extra = dict(headers or {})
    if code == 401:
        extra["WWW-Authenticate"] = "Bearer"
    await _deny(send, code, detail, extra)


router = APIRouter(prefix="/api/auth")


class LoginRequest(BaseModel):
    username: str = Field(..., max_length=64)
    password: str = Field(..., max_length=128)


def current_user(request: Request) -> dict[str, str]:
    if settings.disabled:
        return {"username": "anonymous", "role": "admin"}
    user = request.scope.get("state", {}).get("user")
    if not user:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Unauthenticated")
    return user


def _require_store() -> None:
    if not store_state["ready"]:
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "User store not ready")


def _token_response(user: User) -> dict[str, Any]:
    return {
        "accessToken": issue_token(user.username, user.role, token_version=user.token_version),
        "tokenType": "bearer",
        "expiresIn": settings.ttl_seconds,
        "username": user.username,
        "role": user.role,
    }


@router.post("/login")
async def login(req: LoginRequest) -> dict[str, Any]:
    _require_store()
    user = await authenticate(req.username, req.password)
    await store.audit(user.username, "auth.login", user.username, {})
    return _token_response(user)


@router.get("/me")
async def me(request: Request) -> dict[str, str]:
    return current_user(request)


class PasswordChange(BaseModel):
    currentPassword: str = Field(..., max_length=128)
    newPassword: str = Field(..., max_length=128)


@router.post("/password")
async def change_password(req: PasswordChange, request: Request) -> dict[str, Any]:
    """Any signed-in user. Old tokens stop working (token version bump); a new one is returned."""
    _require_store()
    actor = current_user(request)["username"]
    user = await get_user(actor, fresh=True)
    if user is None:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    if not verify_password(req.currentPassword, user.password_hash):
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Current password is wrong")
    if req.newPassword == req.currentPassword:
        raise AuthError(400, "New password must differ from the current one")
    problems = password_problems(req.newPassword, actor)
    if problems:
        raise AuthError(status.HTTP_400_BAD_REQUEST, "Password needs " + ", ".join(problems))
    user.password_hash = hash_password(req.newPassword)
    user.token_version += 1
    user.password_changed_at = time.time()
    await save_user(user)
    await store.audit(actor, "password.changed", actor, {})
    return _token_response(user)


@router.get("/users")
async def list_users() -> list[dict[str, str]]:
    _require_store()
    return [{"username": u.username, "role": u.role} for u in await store.list()]


# --- Step 13b: admin user management, audit log and settings (admin role) ----------------

admin_router = APIRouter(prefix="/api/admin")


class NewUser(BaseModel):
    username: str = Field(..., max_length=32)
    role: str
    password: str = Field(..., max_length=128)


class UserPatch(BaseModel):
    role: str | None = None
    disabled: bool | None = None


class PasswordReset(BaseModel):
    newPassword: str = Field(..., max_length=128)


async def _target(username: str) -> User:
    _require_store()
    user = await get_user(username, fresh=True)
    if user is None:
        raise AuthError(status.HTTP_404_NOT_FOUND, "User not found")
    return user


async def _active_admins() -> int:
    return sum(1 for u in await store.list() if u.role == "admin" and not u.disabled)


@admin_router.get("/users")
async def admin_users() -> dict[str, Any]:
    _require_store()
    return {"items": [u.public() for u in await store.list()]}


@admin_router.post("/users", status_code=201)
async def admin_create_user(req: NewUser, request: Request) -> dict[str, Any]:
    _require_store()
    actor = current_user(request)["username"]
    if not USERNAME_RE.match(req.username):
        raise AuthError(400, "Username: 3-32 chars, lowercase letters, digits, . _ -")
    if req.role not in ROLES:
        raise AuthError(400, f"Role must be one of {', '.join(ROLES)}")
    problems = password_problems(req.password, req.username)
    if problems:
        raise AuthError(400, "Password needs " + ", ".join(problems))
    user = User(username=req.username, role=req.role, password_hash=hash_password(req.password))
    if not await store.create(user):
        raise AuthError(409, "User already exists")
    await store.audit(actor, "user.created", req.username, {"role": req.role})
    return user.public()


@admin_router.patch("/users/{username}")
async def admin_update_user(username: str, req: UserPatch, request: Request) -> dict[str, Any]:
    actor = current_user(request)["username"]
    user = await _target(username)
    if username == actor and (req.role not in (None, user.role) or req.disabled):
        raise AuthError(400, "You cannot change your own role or disable yourself")
    detail: dict[str, Any] = {}
    if req.role is not None and req.role != user.role:
        if req.role not in ROLES:
            raise AuthError(400, f"Role must be one of {', '.join(ROLES)}")
        if user.role == "admin" and await _active_admins() <= 1:
            raise AuthError(400, "Cannot demote the last active admin")
        detail.update({"from": user.role, "to": req.role})
        user.role = req.role
    if req.disabled is not None and req.disabled != user.disabled:
        if req.disabled and user.role == "admin" and await _active_admins() <= 1:
            raise AuthError(400, "Cannot disable the last active admin")
        user.disabled = req.disabled
        detail["disabled"] = req.disabled
    if detail:
        user.token_version += 1  # sign the user out everywhere
        await save_user(user)
        action = "user.role_changed" if "to" in detail else "user.updated"
        await store.audit(actor, action, username, detail)
    return user.public()


@admin_router.post("/users/{username}/unlock")
async def admin_unlock(username: str, request: Request) -> dict[str, Any]:
    actor = current_user(request)["username"]
    user = await _target(username)
    user.locked_until = 0.0
    user.failed_logins = 0
    await save_user(user)
    await store.audit(actor, "user.unlocked", username, {})
    return user.public()


@admin_router.post("/users/{username}/reset-password")
async def admin_reset_password(
    username: str, req: PasswordReset, request: Request
) -> dict[str, Any]:
    actor = current_user(request)["username"]
    user = await _target(username)
    problems = password_problems(req.newPassword, username)
    if problems:
        raise AuthError(400, "Password needs " + ", ".join(problems))
    user.password_hash = hash_password(req.newPassword)
    user.token_version += 1
    user.locked_until = 0.0
    user.failed_logins = 0
    user.password_changed_at = time.time()
    await save_user(user)
    await store.audit(actor, "password.reset", username, {})
    return user.public()


@admin_router.get("/audit")
async def admin_audit(limit: int = 200) -> dict[str, Any]:
    _require_store()
    return {"items": await store.audit_log(max(1, min(limit, 1000)))}


@admin_router.get("/settings")
async def admin_settings(response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return {
        "userStore": store.kind,
        "userStoreReady": store_state["ready"],
        "tokenTtlSeconds": settings.ttl_seconds,
        "rateLimitPerMin": settings.rate_per_min,
        "loginRateLimitPerMin": settings.login_rate_per_min,
        "lockoutThreshold": settings.lockout_threshold,
        "lockoutSeconds": settings.lockout_seconds,
        "demoUsersSeeded": store_state["seeded"] > 0,
        "authDisabled": settings.disabled,
    }
