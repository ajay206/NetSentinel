import hmac
import logging
import os

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp_server.server import mcp

logger = logging.getLogger(__name__)


class ServiceTokenMiddleware:
    """Pure-ASGI middleware: open /healthz and /readyz; Bearer service token on /mcp.

    The token check is constant-time.

    With token=None (MCP_ALLOW_NO_TOKEN=1, local dev only) /mcp is not protected.
    """

    def __init__(self, app: ASGIApp, token: str | None) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/healthz":
            response = JSONResponse({"status": "ok"})
            await response(scope, receive, send)
            return
        if path == "/readyz":
            # W12: ready = the tool layer is built and /mcp is protected (or explicitly open)
            response = JSONResponse(
                {"status": "ready", "auth": "token" if self.token else "open (dev)"}
            )
            await response(scope, receive, send)
            return

        if self.token and path.startswith("/mcp"):
            auth_header = None
            for name, value in scope.get("headers", []):
                if name == b"authorization":
                    auth_header = value.decode("latin-1")
                    break

            expected = f"Bearer {self.token}"
            if not auth_header or not hmac.compare_digest(auth_header, expected):
                response = JSONResponse(
                    {"detail": "missing or invalid service token"}, status_code=401
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


def build_app() -> ASGIApp:
    """ASGI app with service-token auth. Run as an app factory so importing never fails:

    uvicorn --factory mcp_server.app:build_app --port 8006
    """
    token = os.getenv("MCP_SERVICE_TOKEN", "")
    allow_no_token = os.getenv("MCP_ALLOW_NO_TOKEN", "0") == "1"

    if not token and not allow_no_token:
        raise RuntimeError("MCP_SERVICE_TOKEN is required")

    base_app = mcp.streamable_http_app()

    if not token and allow_no_token:
        logger.warning("MCP_SERVICE_TOKEN not set; running without authentication (dev mode)")

    return ServiceTokenMiddleware(base_app, token or None)
