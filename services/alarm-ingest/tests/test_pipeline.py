from __future__ import annotations

import os

os.environ["DISABLE_KAFKA"] = "1"

import pytest
from alarm_ingest.correlate import Correlator
from alarm_ingest.dedupe import Deduper
from alarm_ingest.enrich import Enricher
from alarm_ingest.main import app
from alarm_ingest.normalize import InvalidAlarm, normalize
from alarm_ingest.pipeline import Pipeline
from fastapi.testclient import TestClient
from netgen import build_topology


@pytest.fixture
def topology():
    return build_topology(seed=42, small=True)


@pytest.fixture
def access_site(topology):
    # Find first access site
    for site in topology.sites:
        if site.kind == "access":
            return site
    pytest.skip("No access site in topology")


@pytest.fixture
def hub_site_with_children(topology):
    # Find a hub site that has children
    for site in topology.sites:
        if site.kind == "hub" and topology.children.get(site.site_id):
            return site
    pytest.skip("No hub site with children in topology")


def test_normalize_aliases():
    raw = {
        "id": "test-1",
        "perceivedSeverity": "CRIT",
        "siteId": "S-1",
    }
    norm = normalize(raw)
    assert norm["perceivedSeverity"] == "critical"

    raw["perceivedSeverity"] = "MAJ"
    norm = normalize(raw)
    assert norm["perceivedSeverity"] == "major"

    raw["perceivedSeverity"] = "MIN"
    norm = normalize(raw)
    assert norm["perceivedSeverity"] == "minor"

    raw["perceivedSeverity"] = "WARN"
    norm = normalize(raw)
    assert norm["perceivedSeverity"] == "warning"

    raw["perceivedSeverity"] = "CLEAR"
    norm = normalize(raw)
    assert norm["perceivedSeverity"] == "cleared"

    raw["perceivedSeverity"] = "INDETERMINATE"
    norm = normalize(raw)
    assert norm["perceivedSeverity"] == "warning"


def test_normalize_missing_fields_defaults():
    raw = {
        "id": "test-2",
        "perceivedSeverity": "major",
        "siteId": "S-2",
    }
    norm = normalize(raw)
    assert norm["alarmType"] == "communicationsAlarm"
    assert norm["probableCause"] == "unknown"
    assert norm["specificProblem"] == ""
    assert norm["sourceSystemId"] == "unknown"
    assert norm["@type"] == "Alarm"
    assert norm["href"] == "/alarm/test-2"
    assert norm["alarmedObject"]["@referredType"] == "Site"
    assert norm["state"] == "raised"
    # alarmRaisedTime should be present and end with Z
    assert norm["alarmRaisedTime"].endswith("Z")


def test_normalize_invalid_severity():
    raw = {
        "id": "test-3",
        "perceivedSeverity": "invalid",
        "siteId": "S-3",
    }
    with pytest.raises(InvalidAlarm):
        normalize(raw)


def test_normalize_invalid_time():
    raw = {
        "id": "test-4",
        "perceivedSeverity": "major",
        "siteId": "S-4",
        "alarmRaisedTime": "not-a-time",
    }
    with pytest.raises(InvalidAlarm):
        normalize(raw)


def test_normalize_z_formatting():
    raw = {
        "id": "test-5",
        "perceivedSeverity": "major",
        "siteId": "S-5",
        "alarmRaisedTime": "2026-10-14T10:00:00Z",
    }
    norm = normalize(raw)
    assert norm["alarmRaisedTime"] == "2026-10-14T10:00:00Z"

    raw["alarmRaisedTime"] = "2026-10-14T10:00:00+00:00"
    norm = normalize(raw)
    assert norm["alarmRaisedTime"] == "2026-10-14T10:00:00Z"


def test_enrich_known_site(topology, access_site):
    enricher = Enricher(topology)
    alarm = {"siteId": access_site.site_id, "perceivedSeverity": "major"}
    enriched = enricher.enrich(alarm)
    enrichment = enriched["enrichment"]
    assert enrichment["known"] is True
    assert enrichment["siteName"] == access_site.name
    assert enrichment["region"] == access_site.region
    assert enrichment["siteKind"] == access_site.kind
    assert enrichment["nodeTypes"] == sorted({node.kind for node in access_site.nodes})
    parents = [p for p, kids in topology.children.items() if access_site.site_id in kids]
    assert enrichment["parentSiteId"] == (parents[0] if parents else None)


def test_enrich_unknown_site(topology):
    enricher = Enricher(topology)
    alarm = {"siteId": "UNKNOWN-SITE", "perceivedSeverity": "major"}
    enriched = enricher.enrich(alarm)
    enrichment = enriched["enrichment"]
    assert enrichment["known"] is False
    assert enrichment["region"] == "Unknown"
    assert enrichment["siteName"] is None
    assert enrichment["siteKind"] is None
    assert enrichment["nodeTypes"] == []
    assert enrichment["parentSiteId"] is None


def test_dedupe_counting_and_window_expiry():
    clock = [0.0]

    def fake_clock():
        return clock[0]

    deduper = Deduper(window_seconds=10.0, clock=fake_clock)
    alarm = {
        "id": "a1",
        "siteId": "S-1",
        "alarmType": "communicationsAlarm",
        "probableCause": "lossOfSignal",
        "specificProblem": "LOS",
        "perceivedSeverity": "major",
        "alarmRaisedTime": "2026-10-14T10:00:00Z",
        "state": "raised",
    }

    # First alarm
    result = deduper.process(alarm)
    assert result["dedup"]["count"] == 1
    assert result["dedup"]["isDuplicate"] is False

    # Second alarm within window
    result = deduper.process(alarm)
    assert result["dedup"]["count"] == 2
    assert result["dedup"]["isDuplicate"] is True

    # Advance clock beyond window
    clock[0] = 11.0
    result = deduper.process(alarm)
    assert result["dedup"]["count"] == 1
    assert result["dedup"]["isDuplicate"] is False


def test_dedupe_cleared_resets():
    clock = [0.0]

    def fake_clock():
        return clock[0]

    deduper = Deduper(window_seconds=10.0, clock=fake_clock)
    alarm = {
        "id": "a1",
        "siteId": "S-1",
        "alarmType": "communicationsAlarm",
        "probableCause": "lossOfSignal",
        "specificProblem": "LOS",
        "perceivedSeverity": "major",
        "alarmRaisedTime": "2026-10-14T10:00:00Z",
        "state": "raised",
    }

    # Raise two alarms
    deduper.process(alarm)
    result = deduper.process(alarm)
    assert result["dedup"]["count"] == 2

    # Send cleared alarm for same site and probableCause
    cleared_alarm = dict(alarm)
    cleared_alarm["id"] = "a2"
    cleared_alarm["perceivedSeverity"] = "cleared"
    cleared_alarm["state"] = "cleared"
    result = deduper.process(cleared_alarm)
    assert result["dedup"]["count"] == 1
    assert result["dedup"]["isDuplicate"] is False

    # Next alarm for same key should start fresh
    result = deduper.process(alarm)
    assert result["dedup"]["count"] == 1
    assert result["dedup"]["isDuplicate"] is False


def test_correlator_root_and_descendant_symptom(topology, hub_site_with_children):
    correlator = Correlator(topology, window_seconds=180.0)
    root_site = hub_site_with_children
    child_site = topology.children[root_site.site_id][0]

    # Root alarm at hub site (critical)
    root_alarm = {
        "id": "root-1",
        "siteId": root_site.site_id,
        "perceivedSeverity": "critical",
        "alarmRaisedTime": "2026-10-14T10:00:00Z",
    }
    result = correlator.correlate(root_alarm)
    assert result["correlation"]["role"] == "root"
    assert result["correlation"]["rootSiteId"] == root_site.site_id
    group_id = result["correlation"]["groupId"]

    # Symptom alarm at child site (major)
    symptom_alarm = {
        "id": "symptom-1",
        "siteId": child_site,
        "perceivedSeverity": "major",
        "alarmRaisedTime": "2026-10-14T10:01:00Z",
    }
    result = correlator.correlate(symptom_alarm)
    assert result["correlation"]["role"] == "symptom"
    assert result["correlation"]["groupId"] == group_id
    assert result["correlation"]["rootSiteId"] == root_site.site_id


def test_correlator_non_related_none(topology, hub_site_with_children):
    correlator = Correlator(topology, window_seconds=180.0)
    root_site = hub_site_with_children
    # Find a site that is not a descendant of root_site
    other_site = None
    for site in topology.sites:
        if site.site_id != root_site.site_id and site.site_id not in topology.children.get(
            root_site.site_id, []
        ):
            # Also ensure not a descendant (but we don't have deep hierarchy in small topology)
            other_site = site
            break
    if other_site is None:
        pytest.skip("No unrelated site found")

    # Root alarm at hub site
    root_alarm = {
        "id": "root-2",
        "siteId": root_site.site_id,
        "perceivedSeverity": "critical",
        "alarmRaisedTime": "2026-10-14T10:00:00Z",
    }
    correlator.correlate(root_alarm)

    # Alarm at unrelated site
    other_alarm = {
        "id": "other-1",
        "siteId": other_site.site_id,
        "perceivedSeverity": "major",
        "alarmRaisedTime": "2026-10-14T10:01:00Z",
    }
    result = correlator.correlate(other_alarm)
    assert result["correlation"]["role"] == "none"
    assert result["correlation"]["groupId"] is None
    assert result["correlation"]["rootSiteId"] is None


def test_pipeline_stats_invalid_and_duplicates(topology):
    pipeline = Pipeline(topology)
    # Valid alarm
    raw = {
        "id": "p1",
        "perceivedSeverity": "major",
        "siteId": "S-1",
    }
    result = pipeline.handle(raw)
    assert result is not None
    assert pipeline.stats["received"] == 1
    assert pipeline.stats["published"] == 1
    assert pipeline.stats["invalid"] == 0
    assert pipeline.stats["duplicates"] == 0

    # Invalid alarm (missing siteId)
    raw_invalid = {"id": "p2", "perceivedSeverity": "major"}
    result = pipeline.handle(raw_invalid)
    assert result is None
    assert pipeline.stats["received"] == 2
    assert pipeline.stats["invalid"] == 1

    # Duplicate alarm (same key)
    raw_dup = dict(raw)
    raw_dup["id"] = "p3"
    result = pipeline.handle(raw_dup)
    assert result is not None
    assert pipeline.stats["duplicates"] == 1


def test_fastapi_endpoints():
    with TestClient(app) as client:
        _check_endpoints(client)


def _check_endpoints(client: TestClient) -> None:
    # healthz
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # readyz (Kafka disabled)
    resp = client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready"}

    # stats
    resp = client.get("/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "received" in data
    assert "published" in data
    assert "invalid" in data
    assert "duplicates" in data
    assert "activeDedupKeys" in data


def _descendants(topology, site_id: str) -> set[str]:
    out: set[str] = set()
    stack = [site_id]
    while stack:
        for child in topology.children.get(stack.pop(), []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def test_correlator_reuses_group_for_repeated_root(topology) -> None:
    site = topology.sites[0].site_id
    corr = Correlator(topology, clock=lambda: 0.0)
    first = corr.correlate({"id": "aaaaaaaa-1", "siteId": site, "perceivedSeverity": "critical"})
    again = corr.correlate({"id": "bbbbbbbb-2", "siteId": site, "perceivedSeverity": "critical"})
    assert first["correlation"]["groupId"] == again["correlation"]["groupId"] == "corr-aaaaaaaa-1"
