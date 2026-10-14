"""W13 clustering: session windows, topology relations, merging, clearing, replay."""

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from incident_service.clustering import (
    IncidentClusterer,
    compression_ratio,
    replay,
)


# ----------------------------------------------------------------------
# Fake topology
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Site:
    id: str
    region: str | None = None
    kind: str = "access"


@dataclass(frozen=True)
class FakeTopology:
    site_by_id: dict[str, Site] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)


def build_topology() -> FakeTopology:
    # Core sites
    core_c1 = Site("C1", region="R1", kind="core")
    core_c2 = Site("C2", region="R2", kind="core")
    # Hubs
    hub_h1 = Site("H1")
    hub_h2 = Site("H2")
    hub_h9 = Site("H9")
    # Access
    acc_a1 = Site("A1")
    acc_a2 = Site("A2")
    acc_a3 = Site("A3")
    acc_a9 = Site("A9")

    site_by_id = {
        s.id: s for s in [core_c1, core_c2, hub_h1, hub_h2, hub_h9, acc_a1, acc_a2, acc_a3, acc_a9]
    }

    children = {
        "C1": ["H1", "H2"],
        "H1": ["A1", "A2"],
        "H2": ["A3"],
        "C2": ["H9"],
        "H9": ["A9"],
    }

    return FakeTopology(site_by_id=site_by_id, children=children)


TOPO = build_topology()
BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


def alarm(
    *,
    alarm_id: str,
    site_id: str,
    raised_offset: int,
    severity: str = "critical",
    dedup_key: str | None = None,
    state: str | None = None,
) -> dict:
    """Helper to build an alarm dict."""
    t = BASE_TIME + timedelta(seconds=raised_offset)
    alarm = {
        "id": alarm_id,
        "siteId": site_id,
        "alarmRaisedTime": t.isoformat().replace("+00:00", "Z"),
        "perceivedSeverity": severity,
    }
    if dedup_key:
        alarm["dedup"] = {"key": dedup_key}
    if state:
        alarm["state"] = state
    return alarm


def ids_of(incidents):
    return {inc["id"] for inc in incidents}


def first_incident(incidents):
    return min(incidents, key=lambda i: i["firstSeen"])


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------
def test_basic_clustering_and_root_selection():
    # LOS at H1, symptoms at A1 and A2 within 2 minutes -> same incident
    alarms = [
        alarm(alarm_id="a1", site_id="H1", raised_offset=0, severity="major"),
        alarm(alarm_id="a2", site_id="A1", raised_offset=30, severity="critical"),
        alarm(alarm_id="a3", site_id="A2", raised_offset=90, severity="minor"),
    ]
    clusterer = IncidentClusterer(TOPO, gap_seconds=300, max_hops=4)
    for a in alarms:
        clusterer.add(a)

    snapshot = clusterer.snapshot()
    assert len(snapshot) == 1
    inc = snapshot[0]
    # root should be H1 (closest to core)
    assert inc["rootSiteId"] == "H1"
    # three sites involved
    assert set(inc["siteIds"]) == {"H1", "A1", "A2"}
    # severity should be the worst (critical)
    assert inc["severity"] == "critical"


def test_separate_incident_for_distant_site():
    alarms = [
        alarm(alarm_id="b1", site_id="H1", raised_offset=0),
        alarm(alarm_id="b2", site_id="A9", raised_offset=0),
    ]
    clusterer = IncidentClusterer(TOPO)
    for a in alarms:
        clusterer.add(a)

    snapshot = clusterer.snapshot()
    assert len(snapshot) == 2
    roots = {inc["rootSiteId"] for inc in snapshot}
    assert roots == {"H1", "A9"}


def test_gap_creates_new_incident():
    alarms = [
        alarm(alarm_id="c1", site_id="A1", raised_offset=0),
        alarm(alarm_id="c2", site_id="A1", raised_offset=400),  # beyond default gap 300
    ]
    clusterer = IncidentClusterer(TOPO)
    for a in alarms:
        clusterer.add(a)

    snapshot = clusterer.snapshot()
    assert len(snapshot) == 2
    # each incident should have its own alarm id
    alarm_ids = {inc["alarmIds"][0] for inc in snapshot}
    assert alarm_ids == {"c1", "c2"}


def test_ancestor_arrival_merges_children():
    # children first, then ancestor H1 later
    alarms = [
        alarm(alarm_id="d1", site_id="A1", raised_offset=10),
        alarm(alarm_id="d2", site_id="A2", raised_offset=20),
        alarm(alarm_id="d3", site_id="H1", raised_offset=30),
    ]
    clusterer = IncidentClusterer(TOPO)
    for a in alarms:
        clusterer.add(a)

    snapshot = clusterer.snapshot()
    assert len(snapshot) == 1
    inc = snapshot[0]
    # root should become H1 after it arrives
    assert inc["rootSiteId"] == "H1"
    assert set(inc["siteIds"]) == {"A1", "A2", "H1"}


def test_bridging_by_common_ancestor():
    # A1 (under H1) and A3 (under H2) only share the core C1, so they stay apart until an
    # alarm at C1 arrives; C1 is an ancestor of both, which merges them
    alarms = [
        alarm(alarm_id="e1", site_id="A1", raised_offset=0),
        alarm(alarm_id="e2", site_id="A3", raised_offset=10),
        alarm(alarm_id="e3", site_id="C1", raised_offset=20),
    ]
    clusterer = IncidentClusterer(TOPO)
    for a in alarms:
        clusterer.add(a)

    snapshot = clusterer.snapshot()
    assert len(snapshot) == 1
    inc = snapshot[0]
    assert set(inc["siteIds"]) == {"A1", "A3", "C1"}
    assert inc["rootSiteId"] == "C1"


def test_cleared_alarms_update_status():
    # Create incident then clear all sites
    alarms = [
        alarm(alarm_id="f1", site_id="A1", raised_offset=0),
        alarm(alarm_id="f2", site_id="A2", raised_offset=10),
        alarm(alarm_id="f3", site_id="A1", raised_offset=20, severity="cleared"),
        alarm(alarm_id="f4", site_id="A2", raised_offset=30, severity="cleared"),
    ]
    clusterer = IncidentClusterer(TOPO)
    for a in alarms:
        clusterer.add(a)

    snapshot = clusterer.snapshot()
    assert len(snapshot) == 1
    inc = snapshot[0]
    assert inc["status"] == "cleared"


def test_cleared_without_active_incident_returns_none():
    # Clear alarm for site never seen before
    alarm_clear = alarm(alarm_id="g1", site_id="A1", raised_offset=0, severity="cleared")
    clusterer = IncidentClusterer(TOPO)
    result = clusterer.add(alarm_clear)
    assert result is None
    assert len(clusterer.incidents) == 0


def test_duplicate_alarm_id_is_ignored():
    a = alarm(alarm_id="dup1", site_id="A1", raised_offset=0)
    b = alarm(alarm_id="dup1", site_id="A2", raised_offset=10)  # same id, different site
    clusterer = IncidentClusterer(TOPO)
    clusterer.add(a)
    result = clusterer.add(b)
    assert result is None
    snapshot = clusterer.snapshot()
    assert len(snapshot) == 1
    inc = snapshot[0]
    # only first site should be present
    assert inc["siteIds"] == ["A1"]


def test_replay_is_deterministic_regardless_of_input_order():
    alarms = [
        alarm(alarm_id="r1", site_id="A1", raised_offset=0),
        alarm(alarm_id="r2", site_id="H1", raised_offset=5),
        alarm(alarm_id="r3", site_id="A2", raised_offset=10),
    ]
    # shuffle with a fixed seed
    shuffled = alarms[:]
    random.Random(1).shuffle(shuffled)

    snap1 = replay(TOPO, alarms)
    snap2 = replay(TOPO, shuffled)

    assert snap1 == snap2
    # ensure ordering of result is by firstSeen then id
    assert [inc["id"] for inc in snap1] == sorted(
        [inc["id"] for inc in snap1], key=lambda i: (snap1[0]["firstSeen"], i)
    )


def test_to_dict_keys_and_iso_format():
    a = alarm(alarm_id="z1", site_id="A1", raised_offset=0, severity="major")
    clusterer = IncidentClusterer(TOPO)
    inc = clusterer.add(a)
    d = inc.to_dict()
    expected_keys = {
        "id",
        "rootSiteId",
        "siteIds",
        "alarmIds",
        "alarmKeys",
        "alarmCount",
        "severity",
        "region",
        "firstSeen",
        "lastSeen",
        "status",
        "version",
    }
    assert set(d.keys()) == expected_keys
    # ISO format ends with Z and no sub‑seconds
    assert d["firstSeen"].endswith("Z")
    assert "T" in d["firstSeen"]


def test_compression_ratio():
    assert compression_ratio(0, 0) == 0.0
    assert compression_ratio(10, 2) == 5.0
    assert compression_ratio(5, 5) == 1.0


def test_core_siblings_stay_separate_and_hub_siblings_merge() -> None:
    c = IncidentClusterer(TOPO)
    c.add(alarm(alarm_id="s1", site_id="A1", raised_offset=0))
    c.add(alarm(alarm_id="s2", site_id="A3", raised_offset=5))  # only shares core C1
    assert len(c.incidents) == 2
    c.add(alarm(alarm_id="s3", site_id="A2", raised_offset=6))  # shares hub H1 with A1
    assert len(c.incidents) == 2
    merged = next(i for i in c.incidents.values() if "A1" in i.site_ids)
    assert merged.site_ids == {"A1", "A2"}


@dataclass(frozen=True)
class Link:
    a: str
    b: str


@dataclass(frozen=True)
class LinkedTopology(FakeTopology):
    links: tuple[Link, ...] = ()


def test_direct_link_relates_both_ends_of_a_cut() -> None:
    topo = LinkedTopology(
        site_by_id=TOPO.site_by_id, children=TOPO.children, links=(Link("H1", "H2"),)
    )
    c = IncidentClusterer(topo)
    c.add(alarm(alarm_id="l1", site_id="H1", raised_offset=0))
    c.add(alarm(alarm_id="l2", site_id="H2", raised_offset=0))
    assert len(c.incidents) == 1
