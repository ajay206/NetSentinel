"""W11: JWT login, RBAC (viewer < operator < admin) and rate limits for the gateway.

HS256 tokens are issued by ``POST /api/auth/login`` against a small user table (demo users
by default; synthetic data only). ``AuthMiddleware`` is pure ASGI so it also guards WebSockets,
where browsers cannot set headers and pass ``?token=`` instead.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs

import jwt
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

ROLES = ("viewer", "operator", "admin")


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
        )


settings = AuthSettings.from_env()


class AuthError(HTTPException):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)


def issue_token(username: str, role: str, now: float | None = None) -> str:
    now = time.time() if now is None else now
    payload = {
        "sub": username,
        "role": role,
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


def check_password(username: str, password: str) -> str | None:
    entry = settings.users.get(username)
    if not entry:
        return None
    stored_pw, role = entry
    if hmac.compare_digest(stored_pw, password):
        return role
    return None


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
    if path.startswith("/api/auth/users"):
        return "admin"
    if path.startswith("/api") or path.startswith("/ws"):
        return "viewer"
    return None


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
            user = {"username": str(claims["sub"]), "role": str(claims["role"])}

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


@router.post("/login")
async def login(req: LoginRequest) -> dict[str, Any]:
    role = check_password(req.username, req.password)
    if not role:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = issue_token(req.username, role)
    return {
        "accessToken": token,
        "tokenType": "bearer",
        "expiresIn": settings.ttl_seconds,
        "username": req.username,
        "role": role,
    }


@router.get("/me")
async def me(request: Request) -> dict[str, str]:
    if settings.disabled:
        return {"username": "anonymous", "role": "admin"}
    user = request.scope.get("state", {}).get("user")
    if not user:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "Unauthenticated")
    return user


@router.get("/users")
async def list_users() -> list[dict[str, str]]:
    return sorted(
        [{"username": u, "role": r} for u, (_, r) in settings.users.items()],
        key=lambda x: x["username"],
    )
