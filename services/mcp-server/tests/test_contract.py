"""contracts/mcp/netsentinel-tools.json must match the live server (regenerate if this fails)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


async def test_mcp_contract_up_to_date():
    spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts/gen_mcp_contract.py")
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    committed = json.loads((ROOT / "contracts/mcp/netsentinel-tools.json").read_text())
    assert committed == await gen.describe()
