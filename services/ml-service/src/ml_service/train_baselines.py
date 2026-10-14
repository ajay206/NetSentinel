from __future__ import annotations

import argparse
import json

from ml_service.eval import evaluate, log_to_mlflow


def main() -> None:
    parser = argparse.ArgumentParser(description="Train/evaluate anomaly baselines")
    parser.add_argument("--experiment", default="anomaly-baselines", help="MLflow experiment name")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--days", type=int, default=7, help="Days of synthetic data")
    parser.add_argument(
        "--cells",
        nargs="+",
        default=["SITE-001-N1-C1", "SITE-002-N1-C1", "SITE-003-N1-C1"],
        help="Cell IDs to evaluate",
    )
    parser.add_argument("--kpi", default="dlThroughputMbps", help="KPI name")
    args = parser.parse_args()

    metrics = evaluate(
        seed=args.seed,
        cells=tuple(args.cells),
        kpi=args.kpi,
        days=args.days,
    )

    params = {
        "seed": args.seed,
        "days": args.days,
        "kpi": args.kpi,
        "cells": args.cells,
    }

    path = log_to_mlflow(metrics, params, args.experiment)
    print(json.dumps({"metrics": metrics, "logged_to": path}, indent=2))


if __name__ == "__main__":
    main()
