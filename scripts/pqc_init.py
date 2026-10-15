#!/usr/bin/env python3
"""One-shot PQC material for the compose stack (Step 21): dev CA, service TLS certs and the
ML-DSA-65 model-signing keypair. Idempotent: existing files are kept.

    python scripts/pqc_init.py --out /pqc --services llm-gateway

Certificates use ECDSA P-256 (authentication); the *key exchange* is hybrid X25519MLKEM768,
set by OPENSSL_CONF (infra/pqc/openssl-hybrid.cnf). See ADR-019.
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from ns_pqc import generate_key


def _write_key(path: Path, key: ec.EllipticCurvePrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    os.chmod(path, 0o640)


def _name(cn: str) -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NetSentinel dev"),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ]
    )


def ensure_ca(out: Path) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    crt, key = out / "ca.crt", out / "ca.key"
    if crt.exists() and key.exists():
        return (
            x509.load_pem_x509_certificate(crt.read_bytes()),
            serialization.load_pem_private_key(key.read_bytes(), None),
        )  # type: ignore[return-value]
    k = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name("NetSentinel dev CA"))
        .issuer_name(_name("NetSentinel dev CA"))
        .public_key(k.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(k, hashes.SHA256())
    )
    _write_key(key, k)
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert, k


def ensure_service(
    out: Path, name: str, ca: x509.Certificate, ca_key: ec.EllipticCurvePrivateKey
) -> bool:
    crt, key = out / f"{name}.crt", out / f"{name}.key"
    if crt.exists() and key.exists():
        return False
    k = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.UTC)
    san = x509.SubjectAlternativeName(
        [
            x509.DNSName(name),
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(name))
        .issuer_name(ca.subject)
        .public_key(k.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=397))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    _write_key(key, k)
    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("/pqc"))
    ap.add_argument("--services", default="llm-gateway")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ca, ca_key = ensure_ca(args.out)
    for svc in filter(None, args.services.split(",")):
        print(f"{svc}: {'created' if ensure_service(args.out, svc, ca, ca_key) else 'kept'}")
    priv, pub = args.out / "model-signing.key", args.out / "model-signing.pub"
    if not (priv.exists() and pub.exists()):
        print("model-signing key:", generate_key(priv, pub))
        os.chmod(priv, 0o640)
    else:
        print("model-signing key: kept")


if __name__ == "__main__":
    main()
