"""Step 21: /api/security/pqc aggregates real-handshake probes + ml-service signature status."""

from __future__ import annotations

import httpx
from api_gateway.pqc_status import PqcStatus


def ml(status: int = 200, body: dict | None = None) -> httpx.MockTransport:
    return httpx.MockTransport(lambda r: httpx.Response(status, json=body or {}))


async def test_status_lists_tls_targets_plaintext_and_model(monkeypatch):
    monkeypatch.setenv("PQC_TLS_TARGETS", "llm-gateway=llm-gateway:8443")
    monkeypatch.setenv("PQC_CA_FILE", "/pqc/ca.crt")
    seen = []

    def probe(host, port, cafile):
        seen.append((host, port, cafile))
        return {
            "target": f"{host}:{port}",
            "hybrid": True,
            "classical": False,
            "group": "X25519MLKEM768",
            "hybridOnly": True,
        }

    sig = {"status": "pass", "alg": "ML-DSA-65", "keyId": "mldsa-x", "policy": "enforce"}
    body = await PqcStatus(lambda: "http://ml", probe, ml(200, sig)).get()
    assert seen == [("llm-gateway", 8443, "/pqc/ca.crt")]
    gw = body["tls"][0]
    assert gw["service"] == "llm-gateway" and gw["tls"] and gw["hybridOnly"]
    plain = {t["service"] for t in body["tls"][1:]}
    assert "ml-service" in plain and all(not t["hybrid"] for t in body["tls"][1:])
    assert body["model"]["status"] == "pass" and body["report"] == "docs/pqc_report.md"


async def test_status_is_cached_and_survives_ml_outage(monkeypatch):
    monkeypatch.delenv("PQC_TLS_TARGETS", raising=False)
    calls = []

    def boom(r):
        calls.append(r)
        raise httpx.ConnectError("down")

    st = PqcStatus(lambda: "http://ml", lambda *a: {}, httpx.MockTransport(boom))
    first = await st.get()
    assert first["model"]["status"] == "unknown" and "unreachable" in first["model"]["reason"]
    assert await st.get() is first and len(calls) == 1
