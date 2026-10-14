"""Synthetic fibre-cut fixtures and a mocked upstream (gateway, ml-service, rag-service)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from copilot_orchestrator.clients.upstream import Upstream

ROOT_ID = "alm-root-0001"
ANOM_TS = "2026-10-14T10:00:00Z"
ANOM_ID = f"ANOM-SITE-010-N1-C1-availabilityPct-{ANOM_TS}"


def _alarm(aid: str, site: str, ts: str, role: str, sev: str = "major") -> dict[str, Any]:
    return {
        "id": aid,
        "alarmType": "communicationsAlarm",
        "perceivedSeverity": sev,
        "probableCause": "lossOfSignal",
        "specificProblem": "LOS",
        "siteId": site,
        "alarmRaisedTime": ts,
        "state": "raised",
        "enrichment": {
            "siteName": site,
            "region": "North",
            "siteKind": "hub" if role == "root" else "access",
            "nodeTypes": ["router"],
            "parentSiteId": "SITE-010" if role != "root" else "SITE-001",
        },
        "dedup": {"key": aid, "count": 1, "firstSeen": ts, "isDuplicate": False},
        "correlation": {"groupId": "corr-1", "rootSiteId": "SITE-010", "role": role},
    }


def fibre_cut_alarms() -> list[dict[str, Any]]:
    alarms = [_alarm(ROOT_ID, "SITE-010", "2026-10-14T10:00:00Z", "root", "critical")]
    alarms += [
        _alarm(f"alm-sym-{i}", f"SITE-01{i}", f"2026-10-14T10:0{i}:00Z", "symptom")
        for i in range(1, 5)
    ]
    # Unrelated site, and an old alarm for SITE-010 outside a 30m window
    other = _alarm("alm-other", "SITE-099", "2026-10-14T10:02:00Z", "none")
    other["correlation"]["rootSiteId"] = None
    other["enrichment"]["parentSiteId"] = "SITE-001"
    alarms.append(other)
    old = _alarm("alm-old", "SITE-010", "2026-10-14T08:00:00Z", "none")
    old["correlation"]["rootSiteId"] = None
    old["enrichment"]["parentSiteId"] = "SITE-001"
    alarms.append(old)
    return alarms


def make_transport(fail: set[str] | None = None) -> httpx.MockTransport:
    fail = fail or set()

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path in fail:
            raise httpx.ConnectError("down")
        if path == "/api/alarms/enriched/recent":
            return httpx.Response(200, json=fibre_cut_alarms())
        if path == "/anomalies":
            kpi = req.url.params["kpi"]
            items = []
            if kpi == "availabilityPct":
                items = [
                    {
                        "cellId": "SITE-010-N1-C1",
                        "region": "North",
                        "ts": ANOM_TS,
                        "value": 12.0,
                        "score": 9.1,
                        "method": "both",
                        "direction": "low",
                    },
                    {
                        "cellId": "SITE-0100-N1-C1",
                        "region": "North",
                        "ts": ANOM_TS,
                        "value": 1.0,
                        "score": 99.0,
                        "method": "both",
                        "direction": "low",
                    },
                ]
            return httpx.Response(200, json={"kpi": kpi, "hours": 1, "items": items})
        if path == "/predict":
            assert json.loads(req.content)["alarm"]["id"] == ROOT_ID
            return httpx.Response(
                200,
                json={
                    "faultType": "fibre_cut",
                    "confidence": 0.9,
                    "probabilities": {},
                    "modelVersion": "v1",
                },
            )
        if path == "/search":
            body = json.loads(req.content)
            assert body["faultType"] == "fibre_cut"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "runbookId": "RB-FIB-001",
                            "title": "Fibre cut on aggregation ring",
                            "section": "Remediation",
                            "snippet": "Confirm protection...",
                            "score": 0.03,
                            "faultType": "fibre_cut",
                        },
                        {
                            "runbookId": "RB-FIB-004",
                            "title": "Microwave backup failover after fibre cut",
                            "section": "Symptoms",
                            "snippet": "Primary fibre LOS...",
                            "score": 0.02,
                            "faultType": "fibre_cut",
                        },
                    ]
                },
            )
        return httpx.Response(404, json={"detail": "nope"})

    return httpx.MockTransport(handler)


@pytest.fixture
def upstream() -> Upstream:
    return Upstream("http://gw", "http://ml", "http://rag", transport=make_transport())


def good_answer() -> dict[str, Any]:
    return {
        "suspectedCause": "Fibre cut on the SITE-010 uplink",
        "faultType": "fibre_cut",
        "confidence": 0.85,
        "evidence": [
            {"text": "Critical LOS at SITE-010 is the correlation root", "sources": [ROOT_ID]},
            {"text": "Availability collapsed on SITE-010-N1-C1", "sources": [ANOM_ID]},
            {"text": "Downstream sites raise LOS", "sources": ["alm-sym-1", "alm-sym-2"]},
        ],
        "steps": [
            {
                "text": "Confirm protection path, dispatch splicing team",
                "runbookId": "RB-FIB-001",
                "section": "Remediation",
            },
        ],
    }
