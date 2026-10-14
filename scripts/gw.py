"""Tiny gateway helper (stdlib only), run inside the tools container or on any Python 3.10+.

    python scripts/gw.py wait [--timeout 240]          # poll /readyz until 200
    python scripts/gw.py token [--as operator]         # print a JWT (demo users)
    python scripts/gw.py call GET /api/ml/anomalies?hours=24 [--as viewer] [--data JSON]

The base URL comes from GATEWAY_URL (default http://localhost:8000). Synthetic data only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("GATEWAY_URL", "http://localhost:8000").rstrip("/")


def _request(method: str, path: str, body: bytes | None = None, token: str | None = None):
    req = urllib.request.Request(BASE + path, data=body, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def token(user: str) -> str:
    payload = json.dumps({"username": user, "password": user}).encode()
    status, text = _request("POST", "/api/auth/login", payload)
    if status != 200:
        raise SystemExit(f"login as {user} failed: HTTP {status}")
    return json.loads(text)["accessToken"]


def wait(timeout: float) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if _request("GET", "/readyz")[0] == 200:
                print(f"gateway ready at {BASE}")
                return 0
        except OSError:
            pass
        time.sleep(3)
    print(f"gateway not ready after {timeout:.0f}s; try: make logs S=api-gateway", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wait")
    w.add_argument("--timeout", type=float, default=240)
    t = sub.add_parser("token")
    t.add_argument("--as", dest="user", default="operator")
    c = sub.add_parser("call")
    c.add_argument("method")
    c.add_argument("path")
    c.add_argument("--as", dest="user", default="viewer")
    c.add_argument("--data", default=None)
    args = p.parse_args(argv)

    if args.cmd == "wait":
        return wait(args.timeout)
    if args.cmd == "token":
        print(token(args.user))
        return 0
    body = args.data.encode() if args.data else None
    status, text = _request(args.method.upper(), args.path, body, token(args.user))
    print(text)
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
