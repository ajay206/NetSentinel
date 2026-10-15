"""W14: Neo4jGraph against a fake async driver (no database needed)."""

from __future__ import annotations

from typing import Any

from topology_service import graph as g
from topology_service.model import from_netgen


class FakeTx:
    def __init__(self, log: list) -> None:
        self.log = log

    async def run(self, cypher: str, **params: Any) -> None:
        self.log.append(("tx", cypher, params))


class FakeSession:
    def __init__(self, log: list) -> None:
        self.log = log

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def execute_write(self, work: Any) -> None:
        self.log.append(("begin",))
        await work(FakeTx(self.log))
        self.log.append(("commit",))


class FakeDriver:
    def __init__(self) -> None:
        self.log: list = []

    def session(self) -> FakeSession:
        return FakeSession(self.log)


async def test_load_replaces_topology_in_one_transaction():
    neo = g.Neo4jGraph.__new__(g.Neo4jGraph)
    neo.driver = FakeDriver()  # type: ignore[assignment]
    topo = from_netgen(seed=42, small=True)
    counts = await neo.load(topo, [{"runbookId": "RB-X", "title": "t", "faultType": "f"}])
    log = neo.driver.log
    assert log[0] == ("begin",) and log[-1] == ("commit",)
    stmts = [e[1] for e in log[1:-1]]
    assert stmts == [g.CLEAR_TOPOLOGY, g.LOAD_SITES, g.LOAD_LINKS, g.LOAD_PARENTS, g.LOAD_RUNBOOKS]
    assert log[2][2]["sites"] == topo.sites and len(log[4][2]["pairs"]) == len(topo.parent)
    assert counts["sites"] == 12 and counts["runbooks"] == 1
    assert "Alarm" not in g.CLEAR_TOPOLOGY
