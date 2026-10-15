#!/usr/bin/env python3
"""Step 21 benchmark: classical X25519 vs hybrid X25519MLKEM768 TLS 1.3 handshakes, and
ML-DSA-65 vs Ed25519 signatures. In-process memory-BIO handshakes (no network noise), one
child process per key-exchange policy because OpenSSL group policy is process-wide.

    uv run python scripts/bench_tls.py --rounds 1000 [--json evals/pqc_bench.json]

Run it inside the Docker image (OpenSSL 3.5) for the numbers in docs/pqc_report.md.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import ssl
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {"classical": "openssl-classical.cnf", "hybrid": "openssl-hybrid.cnf"}


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def handshakes(rounds: int, cert: str, key: str) -> dict:
    sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    sctx.load_cert_chain(cert, key)
    sctx.minimum_version = ssl.TLSVersion.TLSv1_3
    sctx.options |= ssl.OP_NO_TICKET
    cctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    cctx.check_hostname, cctx.verify_mode = False, ssl.CERT_NONE
    times, c2s, s2c = [], 0, 0
    for _ in range(rounds):
        ci, co, si, so = ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO(), ssl.MemoryBIO()
        c = cctx.wrap_bio(ci, co, server_hostname="localhost")
        s = sctx.wrap_bio(si, so, server_side=True)
        t0 = time.perf_counter()
        cdone = sdone = False
        while not (cdone and sdone):
            if not cdone:
                try:
                    c.do_handshake()
                    cdone = True
                except ssl.SSLWantReadError:
                    pass
            data = co.read()
            c2s += len(data)
            si.write(data)
            if not sdone:
                try:
                    s.do_handshake()
                    sdone = True
                except ssl.SSLWantReadError:
                    pass
            data = so.read()
            s2c += len(data)
            ci.write(data)
        times.append((time.perf_counter() - t0) * 1000)
    return {
        "rounds": rounds,
        "p50_ms": round(statistics.median(times), 3),
        "p95_ms": round(_pct(times, 0.95), 3),
        "mean_ms": round(statistics.fmean(times), 3),
        "client_to_server_bytes": c2s // rounds,
        "server_to_client_bytes": s2c // rounds,
        "openssl": ssl.OPENSSL_VERSION,
    }


def signatures(rounds: int) -> dict:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, mldsa

    msg = os.urandom(4096)
    out = {}
    for name, gen in (
        ("Ed25519", ed25519.Ed25519PrivateKey.generate),
        ("ML-DSA-65", mldsa.MLDSA65PrivateKey.generate),
    ):
        k = gen()
        pub = k.public_key()
        t0 = time.perf_counter()
        for _ in range(rounds):
            sig = k.sign(msg)
        t1 = time.perf_counter()
        for _ in range(rounds):
            pub.verify(sig, msg)
        t2 = time.perf_counter()
        raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        out[name] = {
            "sign_us": round((t1 - t0) / rounds * 1e6, 1),
            "verify_us": round((t2 - t1) / rounds * 1e6, 1),
            "signature_bytes": len(sig),
            "public_key_bytes": len(raw),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=1000)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--child", choices=list(POLICIES))
    ap.add_argument("--cert")
    ap.add_argument("--key")
    a = ap.parse_args()
    if a.child:
        print(json.dumps(handshakes(a.rounds, a.cert, a.key)))
        return
    if ssl.OPENSSL_VERSION_INFO < (3, 5):
        sys.exit(
            f"needs OpenSSL >= 3.5 for ML-KEM, have {ssl.OPENSSL_VERSION}; use the Docker image"
        )
    sys.path.insert(0, str(ROOT / "scripts"))
    import pqc_init

    with tempfile.TemporaryDirectory() as d:
        ca, ca_key = pqc_init.ensure_ca(Path(d))
        pqc_init.ensure_service(Path(d), "bench", ca, ca_key)
        res = {
            "platform": (
                f"{platform.system()} {platform.machine()}, Python {platform.python_version()}"
            ),
            "tls": {},
        }
        for pol, cnf in POLICIES.items():
            env = {**os.environ, "OPENSSL_CONF": str(ROOT / "infra/pqc" / cnf)}
            r = subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--child",
                    pol,
                    "--rounds",
                    str(a.rounds),
                    "--cert",
                    f"{d}/bench.crt",
                    "--key",
                    f"{d}/bench.key",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            res["tls"][pol] = json.loads(r.stdout)
    res["signatures"] = signatures(max(50, a.rounds // 10))
    c, h = res["tls"]["classical"], res["tls"]["hybrid"]
    res["delta"] = {
        "p50_ms": round(h["p50_ms"] - c["p50_ms"], 3),
        "p50_pct": round(100 * (h["p50_ms"] / c["p50_ms"] - 1), 1),
        "extra_bytes": (h["client_to_server_bytes"] + h["server_to_client_bytes"])
        - (c["client_to_server_bytes"] + c["server_to_client_bytes"]),
    }
    print(json.dumps(res, indent=2))
    if a.json:
        a.json.write_text(json.dumps(res, indent=2) + "\n")


if __name__ == "__main__":
    main()
