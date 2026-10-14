import json

from incident_service.evaluate import build_dataset, evaluate, main, render_report


def test_build_dataset_deterministic():
    alarms1, truth1 = build_dataset(seed=123, faults=5, noise_ratio=0.2, concurrent=False)
    alarms2, truth2 = build_dataset(seed=123, faults=5, noise_ratio=0.2, concurrent=False)
    assert alarms1 == alarms2
    assert truth1 == truth2
    real_faults = [t for t in truth1 if not t["fault"].startswith("NOISE")]
    assert len(real_faults) == 5


def test_evaluate_sequential():
    alarms, truth = build_dataset(seed=42, faults=4, noise_ratio=0.3, concurrent=False)
    res = evaluate(alarms, truth, gap_seconds=300, max_hops=4)
    assert res["alarms"] == len(alarms)
    assert res["incidents"] >= res["faults"]
    assert res["compressionRatio"] > 1
    assert 0.0 <= res["rootMatchRate"] <= 1.0
    assert res["deterministic"] is True


def test_render_report_contains_headers():
    dummy = [
        (
            "scenario",
            {
                "alarms": 10,
                "incidents": 5,
                "compressionRatio": 2.0,
                "rootMatchRate": 0.5,
                "purity": 0.6,
                "completeness": 0.7,
                "splitFaults": 0,
                "mergedFaults": 0,
                "noiseAbsorbed": 0,
                "deterministic": True,
            },
        )
    ]
    report = render_report(dummy)
    assert "## Incident compression (W13)" in report
    assert "| Scenario | Alarms | Incidents |" in report
    assert "scenario" in report


def test_main_json_output(capsys):
    exit_code = main(["--faults", "4", "--json"])
    assert exit_code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert isinstance(data, dict)
    assert set(data.keys()) == {"sequential", "concurrent pairs", "concurrent, gap 60s"}
