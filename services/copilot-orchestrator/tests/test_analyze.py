from __future__ import annotations

import json

import pytest
from copilot_orchestrator.analyze import analyze, fallback_answer, gather, validate_answer
from copilot_orchestrator.clients.llm import MockLLM, OffLLM
from copilot_orchestrator.clients.upstream import Upstream, select_site_alarms
from copilot_orchestrator.models import AnalyzeRequest, Answer, AnswerInvalid, Context
from pydantic import ValidationError

from .conftest import ANOM_ID, ROOT_ID, fibre_cut_alarms, good_answer, make_transport


def test_answer_schema_rejects_extra_and_empty_evidence():
    with pytest.raises(ValidationError):
        Answer.model_validate({**good_answer(), "extra": 1})
    with pytest.raises(ValidationError):
        Answer.model_validate({**good_answer(), "evidence": []})


def test_request_validation():
    with pytest.raises(ValidationError):
        AnalyzeRequest(site_id="S-12")
    with pytest.raises(ValidationError):
        AnalyzeRequest(site_id="SITE-012", window="0m")
    assert AnalyzeRequest(site_id="SITE-012", window="45m").window_minutes == 45


def test_window_anchored_on_newest_alarm():
    picked = select_site_alarms(fibre_cut_alarms(), "SITE-010", 30)
    ids = [a["id"] for a in picked]
    assert ids[0] == ROOT_ID  # root first
    assert "alm-old" not in ids and "alm-other" not in ids
    assert len(ids) == 5


async def test_gather_filters_anomalies_by_site_prefix(upstream: Upstream):
    ctx, _ = await gather(upstream, AnalyzeRequest(site_id="SITE-010"))
    assert [a.id for a in ctx.anomalies] == [ANOM_ID]  # SITE-0100 excluded
    assert ctx.fault and ctx.fault["faultType"] == "fibre_cut"
    assert [r.runbookId for r in ctx.runbooks] == ["RB-FIB-001", "RB-FIB-004"]


async def test_validate_rejects_unknown_ids(upstream: Upstream):
    ctx, _ = await gather(upstream, AnalyzeRequest(site_id="SITE-010"))
    bad = good_answer()
    bad["evidence"][0]["sources"] = ["made-up-id"]
    bad["steps"][0]["runbookId"] = "RB-XYZ-999"
    with pytest.raises(AnswerInvalid) as exc:
        validate_answer(json.dumps(bad), ctx)
    assert len(exc.value.messages) == 2
    with pytest.raises(AnswerInvalid):
        validate_answer("not json", ctx)


async def test_retry_then_success(upstream: Upstream):
    llm = MockLLM(["{oops", good_answer()])
    res = await analyze(AnalyzeRequest(site_id="SITE-010"), upstream, llm)
    assert res.generatedBy == "llm" and res.attempts == 2
    assert "previous answer was invalid" in llm.calls[1][1]["content"]


async def test_llm_down_falls_back_immediately(upstream: Upstream):
    res = await analyze(AnalyzeRequest(site_id="SITE-010"), upstream, OffLLM())
    assert res.generatedBy == "fallback" and res.attempts == 1 and res.model is None
    assert res.answer.faultType == "fibre_cut"
    assert res.answer.evidence[0].sources == [ROOT_ID]


async def test_always_invalid_falls_back_after_three(upstream: Upstream):
    res = await analyze(AnalyzeRequest(site_id="SITE-010"), upstream, MockLLM(["[]"]))
    assert res.generatedBy == "fallback" and res.attempts == 3 and len(res.errors) == 3


async def test_upstream_failures_degrade_gracefully():
    up = Upstream(
        "http://gw",
        "http://ml",
        "http://rag",
        transport=make_transport({"/predict", "/search", "/anomalies"}),
    )
    res = await analyze(AnalyzeRequest(site_id="SITE-010"), up, OffLLM())
    assert res.answer.faultType == "unknown" and res.answer.steps == []
    assert len(res.warnings) == 3


def test_fallback_without_runbooks_still_valid():
    ctx = Context.model_validate(
        {
            "site_id": "SITE-010",
            "window_minutes": 30,
            "fault": None,
            "runbooks": [],
            "anomalies": [],
            "alarms": [
                {
                    "id": "a1",
                    "siteId": "SITE-010",
                    "specificProblem": "LOS",
                    "perceivedSeverity": "critical",
                    "alarmRaisedTime": "t",
                    "role": "root",
                }
            ],
        }
    )
    ans = fallback_answer(ctx)
    assert ans.steps == [] and ans.evidence[-1].sources == ["a1"]
