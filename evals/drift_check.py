#!/usr/bin/env python3
"""W24 PSI drift check: training distribution vs a 'recent' synthetic window. Exit 1 = drift.

uv run python evals/drift_check.py                 # recent = new seed, same generator
uv run python evals/drift_check.py --shift 1.5     # scale features: shows a drift alert
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from ml_service.drift import features, report

    p = argparse.ArgumentParser()
    p.add_argument("--train-seed", type=int, default=42)
    p.add_argument("--recent-seed", type=int, default=2026)
    p.add_argument("--n", type=int, default=2000)
    p.add_argument("--shift", type=float, default=1.0, help="multiply recent features (demo)")
    p.add_argument("--threshold", type=float, default=0.2)
    p.add_argument("--out")
    a = p.parse_args(argv)
    train = features(a.train_seed, a.n)
    recent = features(a.recent_seed, a.n) * a.shift
    r = report(train, recent, threshold=a.threshold)
    text = json.dumps(r, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text)
    print("DRIFT:", r["status"].upper(), file=sys.stderr)
    return 1 if r["status"] == "drift" else 0


if __name__ == "__main__":
    sys.exit(main())
