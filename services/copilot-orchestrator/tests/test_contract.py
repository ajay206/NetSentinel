"""The committed OpenAPI contract must match the app (regenerate it if this fails)."""

from __future__ import annotations

from pathlib import Path

import yaml
from copilot_orchestrator.api import app

CONTRACT = Path(__file__).resolve().parents[3] / "contracts/openapi/copilot-orchestrator.yaml"


def test_contract_matches_app():
    spec = yaml.safe_load(CONTRACT.read_text())
    live = app.openapi()
    assert set(spec["paths"]) == set(live["paths"])
    assert spec["components"]["schemas"] == live["components"]["schemas"]
