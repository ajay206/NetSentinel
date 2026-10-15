import os
import re
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.backends import BackendError, Backends

DEFAULT_ALLOWED_HOSTS = "localhost:*,127.0.0.1:*,mcp-server:*"
DEFAULT_ALLOWED_ORIGINS = "http://localhost:*,http://127.0.0.1:*"


def _csv(name: str, default: str) -> list[str]:
    return [h.strip() for h in os.getenv(name, default).split(",") if h.strip()]


def transport_security() -> TransportSecuritySettings:
    """DNS-rebinding protection that also accepts the compose service name.

    FastMCP's default only allows localhost, so the copilot calling http://mcp-server:8006 got
    421 "Invalid Host header". Override with MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS (CSV).
    """
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_csv("MCP_ALLOWED_HOSTS", DEFAULT_ALLOWED_HOSTS),
        allowed_origins=_csv("MCP_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS),
    )


mcp = FastMCP(
    "netsentinel",
    transport_security=transport_security(),
    instructions=(
        "NetSentinel MCP Server provides tools for network operations:\n"
        "- get_alarms: recent enriched alarms for a site\n"
        "- kpi_anomalies: KPI anomalies for a site's cells\n"
        "- search_runbooks: search runbooks by query and fault type\n"
        "- predict_fault: predict fault type from an alarm\n"
        "- query_topology: which cells lose service if a link/site/node fails, or a named "
        "graph query\n"
        "- runbook://{runbook_id}: fetch runbook markdown\n"
        "- analyze_site prompt: guided site analysis workflow"
    ),
    stateless_http=True,
    json_response=True,
)

SITE_ID_PATTERN = re.compile(r"^SITE-\d{3}$")
RUNBOOK_ID_PATTERN = re.compile(r"^RB-[A-Z]{3}-\d{3}$")


def validate_site_id(site_id: str) -> None:
    if not SITE_ID_PATTERN.match(site_id):
        raise ValueError("site_id must match ^SITE-\\d{3}$")


def validate_window_minutes(window_minutes: int) -> None:
    if not 1 <= window_minutes <= 720:
        raise ValueError("window_minutes must be between 1 and 720")


def validate_hours(hours: int) -> None:
    if not 1 <= hours <= 24:
        raise ValueError("hours must be between 1 and 24")


def validate_top_k(top_k: int) -> None:
    if not 1 <= top_k <= 10:
        raise ValueError("top_k must be between 1 and 10")


def validate_query(query: str) -> None:
    if not 1 <= len(query) <= 500:
        raise ValueError("query must be 1-500 characters")


def validate_runbook_id(runbook_id: str) -> None:
    if not RUNBOOK_ID_PATTERN.match(runbook_id):
        raise ValueError("runbook_id must match ^RB-[A-Z]{3}-\\d{3}$")


@mcp.tool()
async def get_alarms(site_id: str, window_minutes: int = 30) -> dict[str, Any]:
    """Get recent enriched alarms for a site within a time window.

    Args:
        site_id: Site identifier (format: SITE-XXX)
        window_minutes: Time window in minutes (1-720), anchored on newest alarm

    Returns:
        Dict with siteId, windowMinutes, and alarms list
    """
    validate_site_id(site_id)
    validate_window_minutes(window_minutes)
    backends = Backends()
    try:
        alarms = await backends.alarms_for_site(site_id, window_minutes)
    except BackendError as exc:
        # Raising makes FastMCP return isError=true, which clients treat as a failed call.
        raise RuntimeError(exc.message) from exc
    return {"siteId": site_id, "windowMinutes": window_minutes, "alarms": alarms}


@mcp.tool()
async def kpi_anomalies(site_id: str, hours: int = 1) -> dict[str, Any]:
    """Get KPI anomalies for cells belonging to a site.

    Args:
        site_id: Site identifier (format: SITE-XXX)
        hours: Lookback window in hours (1-24)

    Returns:
        Dict with siteId, hours, and anomalies list
    """
    validate_site_id(site_id)
    validate_hours(hours)
    backends = Backends()
    try:
        anomalies = await backends.anomalies_for_site(site_id, hours)
    except BackendError as exc:
        # Raising makes FastMCP return isError=true, which clients treat as a failed call.
        raise RuntimeError(exc.message) from exc
    return {"siteId": site_id, "hours": hours, "anomalies": anomalies}


@mcp.tool()
async def search_runbooks(
    query: str, fault_type: str | None = None, top_k: int = 3, mode: str = "hybrid"
) -> dict[str, Any]:
    """Search runbooks by query and optional fault type.

    Args:
        query: Search query (1-500 characters)
        fault_type: Optional fault type filter
        top_k: Number of results to return (1-10)
        mode: hybrid (default) or graph (Step 15 Graph RAG: links site/link/cell ids in the
            query to the topology; results carry nodeIds for citations)

    Returns:
        Dict with query and results list
    """
    validate_query(query)
    validate_top_k(top_k)
    if mode not in ("hybrid", "graph"):
        raise ValueError("mode must be hybrid or graph")
    backends = Backends()
    try:
        results = await backends.search_runbooks(query, fault_type, top_k, mode)
    except BackendError as exc:
        # Raising makes FastMCP return isError=true, which clients treat as a failed call.
        raise RuntimeError(exc.message) from exc
    return {"query": query, "mode": mode, "results": results}


@mcp.tool()
async def predict_fault(alarm: dict[str, Any]) -> dict[str, Any]:
    """Predict fault type from an alarm.

    Args:
        alarm: Alarm dictionary (must contain 'id' field)

    Returns:
        ML service prediction result
    """
    if not isinstance(alarm, dict) or "id" not in alarm:
        raise ValueError("alarm must be a dict with an 'id' field")
    backends = Backends()
    try:
        return await backends.predict_fault(alarm)
    except BackendError as exc:
        # Raising makes FastMCP return isError=true, which clients treat as a failed call.
        raise RuntimeError(exc.message) from exc


TOPO_ID_PATTERNS = {
    "link_id": re.compile(r"^LNK-\d{3}$"),
    "site_id": SITE_ID_PATTERN,
    "node_id": re.compile(r"^SITE-\d{3}-[A-Z0-9]{1,8}$"),
}
QUERY_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


@mcp.tool()
async def query_topology(
    link_id: str | None = None,
    site_id: str | None = None,
    node_id: str | None = None,
    query: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Ask the network knowledge graph (Neo4j, W14).

    Give exactly one of link_id, site_id or node_id for an impact analysis ("which cells lose
    service if LNK-012 fails?"), or query with params to run a named read-only catalogue query
    (e.g. query="path_to_core", params={"siteId": "SITE-010"}).

    Args:
        link_id: Failed link (format: LNK-XXX)
        site_id: Failed site (format: SITE-XXX)
        node_id: Failed node (format: SITE-XXX-<node>)
        query: Named query from GET /api/graph/queries
        params: Parameters for the named query

    Returns:
        Impact result (impactedSites with cells, cellsLost, sitesIsolated) or {query, rows}
    """
    given = {
        k: v for k, v in (("link_id", link_id), ("site_id", site_id), ("node_id", node_id)) if v
    }
    if bool(given) == bool(query) or len(given) > 1:
        raise ValueError("give exactly one of link_id, site_id, node_id or query")
    target = None
    if given:
        ((key, value),) = given.items()
        if not TOPO_ID_PATTERNS[key].match(value):
            raise ValueError(f"{key} has an invalid format")
        param = {"link_id": "linkId", "site_id": "siteId", "node_id": "nodeId"}[key]
        target = {param: value}
    elif not QUERY_NAME_PATTERN.match(query or ""):
        raise ValueError("query must be a catalogue name such as path_to_core")
    if params is not None and (not isinstance(params, dict) or len(params) > 5):
        raise ValueError("params must be a dict with at most 5 keys")
    try:
        return await Backends().query_topology(target, query, params or {})
    except BackendError as exc:
        # Raising makes FastMCP return isError=true, which clients treat as a failed call.
        raise RuntimeError(exc.message) from exc


@mcp.resource("runbook://{runbook_id}", mime_type="text/markdown")
async def runbook(runbook_id: str) -> str:
    """Fetch runbook markdown content by ID."""
    validate_runbook_id(runbook_id)
    backends = Backends()
    try:
        data = await backends.get_runbook(runbook_id)
    except BackendError as exc:
        return f"# Error\n\n{exc.message}"
    markdown = data.get("markdown") if isinstance(data, dict) else None
    if not markdown:
        return f"# Runbook Not Found\n\nNo content for {runbook_id}"
    return markdown


@mcp.prompt()
def analyze_site(site_id: str, window: str = "30m") -> str:
    """Guided site analysis: gather evidence with the tools, then answer as cited JSON."""
    return (
        f"Analyze site {site_id} over the last {window}.\n\n"
        "1. get_alarms(site_id, window_minutes) - the first alarm is the root (or most severe).\n"
        "2. kpi_anomalies(site_id, hours=1).\n"
        "3. predict_fault(alarm=<root alarm>).\n"
        "4. search_runbooks(query=<specificProblem + probable cause + fault type>, "
        "fault_type=<predicted>).\n"
        "5. Optionally read runbook://<runbookId> for full steps.\n\n"
        "Answer ONLY with JSON: {suspectedCause, faultType, confidence (0-1), "
        "evidence: [{text, sources: [ids copied exactly from tool results]}], "
        "steps: [{text, runbookId, section}]}. Never invent ids. "
        "Anomaly ids are ANOM-<cellId>-<kpi>-<ts>."
    )
