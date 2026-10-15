"""Step 21: ML-DSA signing (tamper -> fail) and real hybrid-TLS handshakes (OpenSSL >= 3.5)."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

import pytest
from ns_pqc import generate_key, probe_tls, sign_dir, verify_dir

ROOT = Path(__file__).resolve().parents[3]
PQC35 = ssl.OPENSSL_VERSION_INFO >= (3, 5)


@pytest.fixture
def signed(tmp_path):
    keys = tmp_path / "keys"
    kid = generate_key(keys / "k.pem", keys / "p.pem")
    mdir = tmp_path / "fault_classifier" / "v1"
    mdir.mkdir(parents=True)
    (mdir / "model.json").write_text('{"trees": [1, 2, 3]}')
    (mdir / "meta.json").write_text('{"classes": ["fibre_cut"]}')
    card = tmp_path / "card.md"
    card.write_text("# model card\n")
    m = sign_dir(mdir, keys / "k.pem", {"model_card": card})
    assert m["alg"] == "ML-DSA-65" and m["keyId"] == kid
    return mdir, keys, card


def test_signed_model_verifies(signed):
    mdir, keys, card = signed
    v = verify_dir(mdir, keys / "p.pem", {"model_card": card})
    assert v.status == "pass", v.reason
    assert (keys / "k.pem").stat().st_mode & 0o077 == 0  # private key not group/world readable


@pytest.mark.parametrize(
    "tamper, reason",
    [
        (
            lambda d, c: (d / "model.json").write_text('{"trees": [9]}'),
            "digest mismatch: model.json",
        ),
        (lambda d, c: (d / "backdoor.py").write_text("x"), "file set changed"),
        (lambda d, c: (d / "model.json").unlink(), "file set changed"),
        (lambda d, c: c.write_text("# edited card\n"), "digest mismatch: model_card"),
    ],
)
def test_tampered_model_fails(signed, tamper, reason):
    mdir, keys, card = signed
    tamper(mdir, card)
    v = verify_dir(mdir, keys / "p.pem", {"model_card": card})
    assert v.status == "fail" and v.reason.startswith(reason)


def test_altered_manifest_and_foreign_key_fail(signed, tmp_path):
    mdir, keys, _ = signed
    sig = json.loads((mdir / "signature.json").read_text())
    sig["files"]["model.json"] = "0" * 64
    (mdir / "signature.json").write_text(json.dumps(sig))
    assert verify_dir(mdir, keys / "p.pem").reason == "bad signature (manifest altered)"
    generate_key(tmp_path / "o.pem", tmp_path / "o.pub")
    assert verify_dir(mdir, tmp_path / "o.pub").reason == "signed by a different key"


def test_unsigned_model(tmp_path):
    (tmp_path / "model.json").write_text("{}")
    generate_key(tmp_path / "k", tmp_path / "p")
    assert verify_dir(tmp_path, tmp_path / "p").status == "unsigned"


def test_sign_model_cli_exit_codes(signed):
    mdir, keys, _ = signed
    cli = [
        sys.executable,
        str(ROOT / "scripts/sign_model.py"),
        "verify",
        "--pub",
        str(keys / "p.pem"),
        "--model-dir",
        str(mdir),
    ]
    assert subprocess.run(cli, capture_output=True).returncode == 0
    (mdir / "model.json").write_text("tampered")
    r = subprocess.run(cli, capture_output=True, text=True)
    assert r.returncode == 1 and json.loads(r.stdout)["status"] == "fail"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


SERVER = """
import socket, ssl, sys
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(sys.argv[2], sys.argv[3])
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", int(sys.argv[1]))); s.listen(); print("ready", flush=True)
while True:
    c, _ = s.accept()
    try:
        ctx.wrap_socket(c, server_side=True).close()
    except (ssl.SSLError, OSError):
        c.close()
"""


@pytest.fixture(scope="module")
def certs(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("pqc_init", ROOT / "scripts/pqc_init.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path_factory.mktemp("pqc")
    ca, ca_key = mod.ensure_ca(out)
    assert mod.ensure_service(out, "llm-gateway", ca, ca_key) is True
    assert mod.ensure_service(out, "llm-gateway", ca, ca_key) is False  # idempotent
    return out


def _serve(conf: str, certs: Path) -> tuple[subprocess.Popen, int]:
    port = _free_port()
    env = {**os.environ, "OPENSSL_CONF": str(ROOT / "infra/pqc" / conf)}
    p = subprocess.Popen(
        [
            sys.executable,
            "-c",
            SERVER,
            str(port),
            str(certs / "llm-gateway.crt"),
            str(certs / "llm-gateway.key"),
        ],
        env=env,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert p.stdout and p.stdout.readline().strip() == "ready"
    time.sleep(0.1)
    return p, port


@pytest.mark.skipif(not PQC35, reason="needs OpenSSL >= 3.5 (ML-KEM); use the Docker image")
@pytest.mark.parametrize(
    "conf, hybrid, classical",
    [
        ("openssl-hybrid.cnf", True, False),
        ("openssl-hybrid-pref.cnf", True, True),
        ("openssl-classical.cnf", False, True),
    ],
)
def test_probe_real_handshakes(certs, conf, hybrid, classical):
    p, port = _serve(conf, certs)
    try:
        r = probe_tls("localhost", port, str(certs / "ca.crt"))
    finally:
        p.kill()
    assert (r["hybrid"], r["classical"]) == (hybrid, classical), r
    assert r["hybridOnly"] is (hybrid and not classical)
    assert r["group"] == ("X25519MLKEM768" if hybrid else "X25519")


@pytest.mark.skipif(not PQC35, reason="needs OpenSSL >= 3.5")
def test_probe_rejects_untrusted_ca(certs, tmp_path):
    p, port = _serve("openssl-hybrid.cnf", certs)
    other = tmp_path / "other"
    other.mkdir()
    spec = importlib.util.spec_from_file_location("pqc_init", ROOT / "scripts/pqc_init.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ensure_ca(other)
    try:
        r = probe_tls("localhost", port, str(other / "ca.crt"))
    finally:
        p.kill()
    assert r["hybrid"] is False and "CERTIFICATE_VERIFY_FAILED" in r["hybridDetail"]
