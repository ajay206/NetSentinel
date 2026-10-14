"""The committed W11 gateway contract matches the app (regenerate: make gateway-contract)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_gateway_auth_contract_is_current() -> None:
    spec = importlib.util.spec_from_file_location(
        "gen_gateway_auth_contract", ROOT / "scripts/gen_gateway_auth_contract.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    committed = yaml.safe_load((ROOT / "contracts/openapi/api-gateway-auth.yaml").read_text())
    assert committed == yaml.safe_load(yaml.safe_dump(mod.build(), sort_keys=False))
