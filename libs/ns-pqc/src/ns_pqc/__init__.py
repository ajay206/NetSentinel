"""Post-quantum helpers (Step 21, W21): ML-DSA model signing and hybrid-TLS probing.

* Model signing: a manifest of SHA-256 digests over a model directory (plus optional model
  card) signed with ML-DSA-65 (FIPS 204) via ``cryptography``. ``verify_dir`` is used on model
  load (ml-service), in CI and by ``scripts/sign_model.py``.
* TLS: OpenSSL 3.5 implements X25519MLKEM768 natively; group policy is set with an
  ``OPENSSL_CONF`` file (``Groups = ...``), process-wide. ``probe_tls`` therefore runs one child
  process per policy (hybrid-only, classical-only) and reports which handshakes succeed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import ssl
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import mldsa

ALG = "ML-DSA-65"
SIG_FILE = "signature.json"
HYBRID_GROUP = "X25519MLKEM768"
CLASSICAL_GROUP = "X25519"

_KEYS = {
    "ML-DSA-44": mldsa.MLDSA44PrivateKey,
    "ML-DSA-65": mldsa.MLDSA65PrivateKey,
    "ML-DSA-87": mldsa.MLDSA87PrivateKey,
}


# --------------------------------------------------------------------------- signing
def generate_key(priv_path: Path, pub_path: Path, alg: str = ALG) -> str:
    """Write a new ML-DSA keypair (PKCS#8 / SPKI PEM). Returns the key id."""
    key = _KEYS[alg].generate()
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    os.chmod(priv_path, 0o600)
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pub_path.write_bytes(pub)
    return key_id(pub)


def key_id(pub_pem: bytes) -> str:
    return "mldsa-" + hashlib.sha256(pub_pem).hexdigest()[:16]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(manifest: dict[str, Any]) -> bytes:
    body = {k: v for k, v in manifest.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def sign_dir(
    model_dir: Path, priv_path: Path, extra: dict[str, Path] | None = None, alg: str = ALG
) -> dict[str, Any]:
    """Sign every file in ``model_dir`` (except the signature) plus ``extra`` (e.g. the card)."""
    key = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
    if not isinstance(key, _KEYS[alg]):
        raise ValueError(f"key is not {alg}")
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    files = {
        p.name: _digest(p)
        for p in sorted(model_dir.iterdir())
        if p.is_file() and p.name != SIG_FILE
    }
    extras = {name: _digest(p) for name, p in (extra or {}).items()}
    manifest: dict[str, Any] = {
        "alg": alg,
        "keyId": key_id(pub),
        "files": files,
        "extra": extras,
        "signedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    manifest["signature"] = base64.b64encode(key.sign(_canonical(manifest))).decode()
    (model_dir / SIG_FILE).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


@dataclass
class Verify:
    status: str  # pass | fail | unsigned
    reason: str
    alg: str | None = None
    keyId: str | None = None
    signedAt: str | None = None
    verifiedAt: str = ""

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_dir(model_dir: Path, pub_path: Path, extra: dict[str, Path] | None = None) -> Verify:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    sig_path = model_dir / SIG_FILE
    if not sig_path.exists():
        return Verify("unsigned", f"no {SIG_FILE}", verifiedAt=now)
    try:
        m = json.loads(sig_path.read_text())
        pub_pem = pub_path.read_bytes()
        pub = serialization.load_pem_public_key(pub_pem)
    except (OSError, ValueError) as exc:
        return Verify("fail", f"unreadable signature or key: {type(exc).__name__}", verifiedAt=now)
    base = Verify("fail", "", m.get("alg"), m.get("keyId"), m.get("signedAt"), now)
    if m.get("alg") not in _KEYS or not isinstance(
        pub, mldsa.MLDSA65PublicKey | mldsa.MLDSA44PublicKey | mldsa.MLDSA87PublicKey
    ):
        base.reason = "unsupported algorithm"
        return base
    if m.get("keyId") != key_id(pub_pem):
        base.reason = "signed by a different key"
        return base
    try:
        pub.verify(base64.b64decode(m["signature"]), _canonical(m))
    except (InvalidSignature, KeyError, ValueError):
        base.reason = "bad signature (manifest altered)"
        return base
    present = {p.name for p in model_dir.iterdir() if p.is_file() and p.name != SIG_FILE}
    if present != set(m["files"]):
        base.reason = f"file set changed: {sorted(present ^ set(m['files']))}"
        return base
    for name, digest in m["files"].items():
        if _digest(model_dir / name) != digest:
            base.reason = f"digest mismatch: {name}"
            return base
    for name, path in (extra or {}).items():
        if m.get("extra", {}).get(name) != (_digest(path) if path.exists() else None):
            base.reason = f"digest mismatch: {name}"
            return base
    base.status, base.reason = (
        "pass",
        f"{len(m['files'])} files + {len(m.get('extra', {}))} extra verified",
    )
    return base


# --------------------------------------------------------------------------- TLS
def openssl_conf(groups: str) -> str:
    return (
        "openssl_conf = openssl_init\n[openssl_init]\nssl_conf = ssl_sect\n"
        f"[ssl_sect]\nsystem_default = sys\n[sys]\nGroups = {groups}\n"
    )


def _handshake(host: str, port: int, cafile: str | None, timeout: float) -> str:
    ctx = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    import socket

    with socket.create_connection((host, port), timeout=timeout) as raw:
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            return tls.version() or "?"


def probe_tls(
    host: str, port: int, cafile: str | None = None, timeout: float = 3.0
) -> dict[str, Any]:
    """Which key-exchange policies does ``host:port`` accept? (one child process per policy)"""
    out: dict[str, Any] = {"target": f"{host}:{port}"}
    for label, group in (("hybrid", HYBRID_GROUP), ("classical", CLASSICAL_GROUP)):
        with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as f:
            f.write(openssl_conf(group))
        env = {**os.environ, "OPENSSL_CONF": f.name}
        args = [
            sys.executable,
            "-m",
            "ns_pqc",
            "handshake",
            host,
            str(port),
            cafile or "",
            str(timeout),
        ]
        try:
            r = subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout + 5)
            ok, detail = r.returncode == 0, (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]
        except subprocess.TimeoutExpired:
            ok, detail = False, ["timeout"]
        finally:
            os.unlink(f.name)
        out[label] = ok
        out[f"{label}Detail"] = detail[0][:160]
    out["group"] = (
        HYBRID_GROUP if out["hybrid"] else (CLASSICAL_GROUP if out["classical"] else None)
    )
    out["hybridOnly"] = bool(out["hybrid"] and not out["classical"])
    return out


def _main(argv: list[str]) -> int:
    if argv[:1] == ["handshake"]:
        host, port, cafile, timeout = argv[1], int(argv[2]), argv[3] or None, float(argv[4])
        try:
            print(_handshake(host, port, cafile, timeout))
            return 0
        except (OSError, ssl.SSLError) as exc:
            print(f"{type(exc).__name__}: {exc}")
            return 1
    print("usage: python -m ns_pqc handshake HOST PORT CAFILE TIMEOUT", file=sys.stderr)
    return 2
