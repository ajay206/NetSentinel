"""evals/redteam.jsonl: injections are blocked, PII is redacted by type, NOC text is untouched."""

import json
from pathlib import Path

import pytest
from llm_gateway import guard, pii

ROWS = [
    json.loads(line)
    for line in (Path(__file__).resolve().parents[3] / "evals" / "redteam.jsonl")
    .read_text()
    .splitlines()
    if line.strip()
]


def test_redteam_set_is_balanced():
    kinds = {r["kind"] for r in ROWS}
    assert kinds == {"injection", "pii", "benign"} and len(ROWS) >= 40


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_redteam(row):
    verdict = guard.check(row["text"])
    red = pii.redact(row["text"])
    if row["expect"] == "block":
        assert verdict.flagged, row["text"]
    else:
        assert not verdict.flagged, (verdict.reasons, row["text"])
    if row["expect"] == "redact":
        assert set(red.counts) == set(row["types"]), red.text
    elif row["expect"] == "allow":
        assert red.total == 0 and red.text == row["text"], red.text


def test_redteam_noc_ids_survive_redaction():
    text = (
        "SITE-010-N1-C2 alm-root-0001 RB-FIB-001 LNK-010 2026-10-15T08:00:00Z 99.95% 5.26.0 :8080"
    )
    assert pii.redact(text).text == text
