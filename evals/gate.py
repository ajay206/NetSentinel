#!/usr/bin/env python3
"""W24 eval gate CLI. Exit 1 = blocked.

uv run python evals/gate.py --model-dir models/fault_classifier/v...   # score one model
uv run python evals/gate.py --train                                    # train + gate (CI)
uv run python evals/gate.py --train --degrade                          # shows a blocked model
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

CFG = Path(__file__).with_name("gate_thresholds.json")


def _train(out: str, seed: int, degrade: bool) -> Path:
    from ml_service import train_xgb

    if degrade:  # deliberately broken labels: the gate must block this
        orig = train_xgb.make_dataset

        def bad(*a, **k):
            alarms, ctx, labels, ts = orig(*a, **k)
            return alarms, ctx, np.random.default_rng(0).permutation(labels), ts

        train_xgb.make_dataset = bad
    train_xgb.train(seed=seed, out_dir=out, register=False)
    return next((Path(out) / "fault_classifier").iterdir())


def main(argv: list[str] | None = None) -> int:
    from ml_service.gate import run_gate

    p = argparse.ArgumentParser()
    p.add_argument("--model-dir")
    p.add_argument("--train", action="store_true")
    p.add_argument("--degrade", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--config", default=str(CFG))
    p.add_argument("--out", help="also write the result JSON here")
    a = p.parse_args(argv)
    if a.train:
        model_dir = _train(tempfile.mkdtemp(), a.seed, a.degrade)
    elif a.model_dir:
        model_dir = Path(a.model_dir)
    else:
        p.error("--model-dir or --train")
    result = run_gate(model_dir, Path(a.config))
    text = json.dumps(result, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text)
    print("EVAL GATE:", "PASS" if result["passed"] else "BLOCKED", file=sys.stderr)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
