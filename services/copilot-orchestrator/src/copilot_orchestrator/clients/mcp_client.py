"""W10 path: gather evidence by calling mcp-server tools over MCP (streamable HTTP)."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from copilot_orchestrator.clients.upstream import ToolRecorder, rag_mode

CALL_TIMEOUT = timedelta(seconds=float(os.getenv("MCP_CALL_TIMEOUT_S", "15")))

SessionFactory = Callable[[], AbstractAsyncContextManager[ClientSession]]


def http_session_factory(url: str, token: str | None, timeout: float = 10.0) -> SessionFactory:
    """Open an MCP session to ``url`` (e.g. http://mcp-server:8006/mcp) with the service token."""

    @asynccontextmanager
    async def _open() -> AsyncIterator[ClientSession]:
        headers = {"Authorization": f"Bearer {token}"} if token else None
        async with streamablehttp_client(url, headers=headers, timeout=timeout) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                yield session

    return _open


class McpUpstream(ToolRecorder):
    """Same interface as ``Upstream`` but every call is an MCP ``tools/call``.

    One MCP session is opened lazily on the first call and reused for the whole analyze
    request; ``aclose()`` ends it. Failures become warnings, like the HTTP path.
    """

    transport_name = "mcp"

    def __init__(self, session_factory: SessionFactory) -> None:
        super().__init__()
        self._factory = session_factory
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._broken = False

    @classmethod
    def from_env(cls) -> McpUpstream:
        url = os.getenv("MCP_URL", "http://localhost:8006/mcp")
        return cls(http_session_factory(url, os.getenv("MCP_SERVICE_TOKEN") or None))

    async def _get_session(self) -> ClientSession | None:
        if self._session is None and not self._broken:
            stack = AsyncExitStack()
            try:
                self._session = await stack.enter_async_context(self._factory())
                self._stack = stack
            except Exception as exc:  # connection refused, 401, handshake errors...
                self._broken = True
                await stack.aclose()
                self.warnings.append(f"mcp-server unavailable: {type(exc).__name__}")
        return self._session

    async def _call(self, tool: str, args: dict[str, Any]) -> dict[str, Any] | None:
        session = await self._get_session()
        if session is None:
            return None
        try:
            result = await session.call_tool(tool, args, read_timeout_seconds=CALL_TIMEOUT)
        except Exception as exc:
            self.warnings.append(f"{tool} failed: {type(exc).__name__}")
            return None
        if result.isError:
            self.warnings.append(f"{tool} returned an error")
            return None
        if isinstance(result.structuredContent, dict):
            return result.structuredContent
        for block in result.content:  # fall back to JSON text content
            text = getattr(block, "text", None)
            if text:
                try:
                    data = json.loads(text)
                except ValueError:
                    continue
                if isinstance(data, dict):
                    return data
        self.warnings.append(f"{tool} returned no structured content")
        return None

    async def _alarms_for_site(self, site_id: str, window_minutes: int) -> list[dict[str, Any]]:
        data = await self._call(
            "get_alarms", {"site_id": site_id, "window_minutes": window_minutes}
        )
        return list((data or {}).get("alarms", []))

    async def _anomalies_for_site(self, site_id: str, hours: int) -> list[dict[str, Any]]:
        data = await self._call("kpi_anomalies", {"site_id": site_id, "hours": hours})
        return list((data or {}).get("anomalies", []))

    async def _predict(self, alarm: dict[str, Any]) -> dict[str, Any] | None:
        return await self._call("predict_fault", {"alarm": alarm})

    async def _runbooks(self, query: str, fault_type: str | None) -> list[dict[str, Any]]:
        data = await self._call(
            "search_runbooks",
            {"query": query[:500], "fault_type": fault_type, "top_k": 3, "mode": rag_mode()},
        )
        return list((data or {}).get("results", []))

    async def aclose(self) -> None:
        if self._stack is not None:
            stack, self._stack, self._session = self._stack, None, None
            try:
                await stack.aclose()
            except Exception as exc:
                self.warnings.append(f"mcp session close failed: {type(exc).__name__}")
