"""contracts/openapi/ticket-service.yaml must match the app (make ticket-contract)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_ticket_contract_up_to_date():
    spec = importlib.util.spec_from_file_location(
        "gen_ticket", ROOT / "scripts/gen_ticket_contract.py"
    )
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    committed = (ROOT / "contracts/openapi/ticket-service.yaml").read_text()
    assert committed == gen.build()
    assert "/tickets/drafts" in committed and "/audit/verify" in committed
