import re
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.backends import BackendError, Backends

mcp = FastMCP(
    "netsentinel",
    instructions=(
        "NetSentinel MCP Server provides tools for network operations:\n"
        "- get_alarms: recent enriched alarms for a site\n"
        "- kpi_anomalies: KPI anomalies for a site's cells\n"
        "- search_runbooks: search runbooks by query and fault type\n"
        "- predict_fault: predict fault type from an alarm\n"
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
    query: str, fault_type: str | None = None, top_k: int = 3
) -> dict[str, Any]:
    """Search runbooks by query and optional fault type.

    Args:
        query: Search query (1-500 characters)
        fault_type: Optional fault type filter
        top_k: Number of results to return (1-10)

    Returns:
        Dict with query and results list
    """
    validate_query(query)
    validate_top_k(top_k)
    backends = Backends()
    try:
        results = await backends.search_runbooks(query, fault_type, top_k)
    except BackendError as exc:
        # Raising makes FastMCP return isError=true, which clients treat as a failed call.
        raise RuntimeError(exc.message) from exc
    return {"query": query, "results": results}


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
