#!/usr/bin/env python3
"""ML-DSA model signing (Step 21). Signs a model version directory and, optionally, its card.

    uv run python scripts/sign_model.py keygen --key .pqc/signing.key --pub .pqc/signing.pub
    uv run python scripts/sign_model.py sign --alg ML-DSA-65 --key .pqc/signing.key \\
        --model-dir models/fault_classifier/<version> --card docs/model_card_fault_classifier.md
    uv run python scripts/sign_model.py verify --pub .pqc/signing.pub --model-dir ... [--card ...]

``verify`` exits 1 unless the result is ``pass`` (used by .github/workflows/verify-model.yml).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ns_pqc import generate_key, sign_dir, verify_dir


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ML-DSA model signing")
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("--key", type=Path, required=True)
    k.add_argument("--pub", type=Path, required=True)
    k.add_argument("--alg", default="ML-DSA-65", choices=["ML-DSA-44", "ML-DSA-65", "ML-DSA-87"])
    for name in ("sign", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--model-dir", type=Path, required=True)
        p.add_argument("--card", type=Path)
        if name == "sign":
            p.add_argument("--key", type=Path, required=True)
            p.add_argument(
                "--alg", default="ML-DSA-65", choices=["ML-DSA-44", "ML-DSA-65", "ML-DSA-87"]
            )
        else:
            p.add_argument("--pub", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "keygen":
        print(json.dumps({"keyId": generate_key(a.key, a.pub, a.alg), "pub": str(a.pub)}))
        return 0
    extra = {"model_card": a.card} if a.card else None
    if a.cmd == "sign":
        m = sign_dir(a.model_dir, a.key, extra, a.alg)
        print(json.dumps({"keyId": m["keyId"], "alg": m["alg"], "files": len(m["files"])}))
        return 0
    v = verify_dir(a.model_dir, a.pub, extra)
    print(json.dumps(v.dict()))
    return 0 if v.status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
