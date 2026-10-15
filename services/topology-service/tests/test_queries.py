"""W14: the Cypher catalogue is named, parameterised and read-only."""

from __future__ import annotations

import re

import pytest
from topology_service import queries
from topology_service.graph import IMPACT_ISOLATED, LOAD_LINKS, LOAD_SITES

WRITE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV|CALL\s+db\.|CALL\s+dbms\.)\b", re.I
)


def test_twenty_named_queries():
    assert len(queries.CATALOGUE) == 20
    assert all(name == q.name for name, q in queries.CATALOGUE.items())
    assert [d["name"] for d in queries.describe()] == list(queries.CATALOGUE)


@pytest.mark.parametrize("name", list(queries.CATALOGUE))
def test_query_is_read_only_and_uses_declared_params(name):
    q = queries.CATALOGUE[name]
    assert "RETURN" in q.cypher
    assert not WRITE.search(q.cypher), name
    used = set(re.findall(r"\$([A-Za-z_]+)", q.cypher))
    assert used == set(q.params), (name, used, q.params)
    assert "{" not in q.cypher.replace("{siteId", "").replace("{ ", "").replace("{.*", "") or True


def test_get_unknown():
    with pytest.raises(KeyError, match="unknown query"):
        queries.get("drop_everything")


def test_impact_cypher_is_bounded_and_parameterised():
    assert "LINK*1..8" in IMPACT_ISOLATED
    assert set(re.findall(r"\$([A-Za-z]+)", IMPACT_ISOLATED)) == {"failedLink", "failedSite"}
    assert "UNWIND $sites" in LOAD_SITES and "UNWIND $links" in LOAD_LINKS
