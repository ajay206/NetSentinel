"""contracts/openapi/topology-service.yaml must match the app (make topology-contract)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_topology_contract_up_to_date():
    spec = importlib.util.spec_from_file_location(
        "gen_topo", ROOT / "scripts/gen_topology_contract.py"
    )
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    committed = (ROOT / "contracts/openapi/topology-service.yaml").read_text()
    assert committed == gen.build()
    assert "/graph/impact" in committed and "/graph/queries/{name}" in committed
