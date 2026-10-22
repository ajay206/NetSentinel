#!/usr/bin/env python3
"""W22: quick check that the obs stack is up and scraping the gateway (stdlib only)."""

from __future__ import annotations

import json
import sys
import urllib.request

CHECKS = {
    "prometheus": "http://127.0.0.1:9090/-/ready",
    "grafana": "http://127.0.0.1:3000/api/health",
    "langfuse": "http://127.0.0.1:3001/api/public/health",
    "mlflow": "http://127.0.0.1:5000/health",
}


def get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310 (localhost only)
            return r.status, r.read()
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc).encode()


def main() -> int:
    ok = True
    for name, url in CHECKS.items():
        code, _ = get(url)
        print(f"{name:11s} {'up' if code == 200 else 'DOWN'} ({url})")
        ok &= code == 200
    code, body = get("http://127.0.0.1:9090/api/v1/targets?state=active")
    if code == 200:
        targets = json.loads(body)["data"]["activeTargets"]
        for t in targets:
            print(f"target     {t['labels'].get('job'):15s} {t['health']}")
        ok &= any(t["labels"].get("job") == "api-gateway" and t["health"] == "up" for t in targets)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
