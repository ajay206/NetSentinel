#!/usr/bin/env python3
"""W24: register a gated model in MLflow and move the `champion` alias. No silent swaps:

* refuses unless ``<version>.gate.json`` (written by evals/gate.py) says passed;
* registers a new version of ``netsentinel-fault-classifier`` with the gate metrics as tags;
* moves the ``champion`` alias only with ``--promote`` (CI does that on main / schedule).

Without ``MLFLOW_TRACKING_URI`` it prints what it would do and exits 0 (CI has no MLflow).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

MODEL_NAME = "netsentinel-fault-classifier"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", required=True)
    p.add_argument("--promote", action="store_true")
    a = p.parse_args(argv)
    mdir = Path(a.model_dir)
    gate_path = mdir.parent / f"{mdir.name}.gate.json"
    if not gate_path.exists():
        print(f"no {gate_path.name}: run evals/gate.py first", file=sys.stderr)
        return 2
    gate = json.loads(gate_path.read_text())
    if not gate.get("passed"):
        print("gate did not pass: refusing to register", gate.get("reasons"), file=sys.stderr)
        return 1
    uri = os.getenv("MLFLOW_TRACKING_URI")
    if not uri:
        alias = " and set alias champion" if a.promote else ""
        f1 = gate["metrics"]["macro_f1"]
        print(f"[dry-run] would register {mdir.name} as {MODEL_NAME}{alias}; macro_f1={f1}")
        return 0
    import mlflow  # type: ignore[import-not-found]
    from mlflow import MlflowClient  # type: ignore[import-not-found]

    mlflow.set_tracking_uri(uri)
    with mlflow.start_run(run_name=f"gate_{mdir.name}") as run:
        mlflow.log_metrics({k: v for k, v in gate["metrics"].items() if isinstance(v, float)})
        mlflow.log_artifacts(str(mdir), artifact_path="model")
    mv = mlflow.register_model(f"runs:/{run.info.run_id}/model", MODEL_NAME)
    client = MlflowClient()
    client.set_model_version_tag(MODEL_NAME, mv.version, "eval_gate", "pass")
    client.set_model_version_tag(MODEL_NAME, mv.version, "local_version", mdir.name)
    if a.promote:
        client.set_registered_model_alias(MODEL_NAME, "champion", mv.version)
    print(f"registered {MODEL_NAME} v{mv.version}{' (champion)' if a.promote else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
