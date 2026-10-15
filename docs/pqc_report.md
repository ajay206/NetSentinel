# Post-quantum report (Step 21, W21)

Measured with `scripts/bench_tls.py --rounds 1000` (raw output: `evals/pqc_bench.json`) on
Linux x86_64, Python 3.12.14, OpenSSL 3.5.8 25 Aug 2026, 8 vCPU Intel Xeon (dev box). The same OpenSSL 3.5 line ships in
the `python:3.12-slim-trixie` service images; rerun inside Docker with `make pqc-bench`.
Handshakes run in-process over memory BIOs (no network), TLS 1.3, ECDSA P-256 certificate,
no session resumption. Each key-exchange policy runs in its own process because OpenSSL group
policy is process-wide (`OPENSSL_CONF`, `infra/pqc/*.cnf`).

## TLS 1.3 handshake: X25519 vs hybrid X25519MLKEM768

| Key exchange | p50 ms | p95 ms | mean ms | client→server B | server→client B |
|---|---:|---:|---:|---:|---:|
| X25519 (classical) | 0.503 | 1.036 | 0.586 | 597 | 939 |
| X25519MLKEM768 (hybrid) | 0.627 | 0.79 | 0.648 | 1538 | 2026 |

- **Latency:** +0.124 ms at p50 (+24.7%). The p95 was lower for hybrid in this run (0.79 vs 1.036 ms), which is scheduler noise at sub-millisecond scale. In absolute terms, ML-KEM costs about a tenth of a millisecond per full handshake.
- **Bytes:** +2028 B per handshake. Server→client grows by 1087 B, about the 1,088 B ML-KEM-768 ciphertext. Client→server grows by 941 B rather than the full 1,184 B encapsulation key, because the classical ClientHello is padded to about 512 B (padding extension) and the hybrid one is not.
- **What it means here:** the copilot → llm-gateway connection is long-lived (httpx keep-alive) and an LLM call takes hundreds of ms, so hybrid key exchange is free in practice. It protects prompts (alarm notes, operator text) against harvest-now-decrypt-later.

## Signatures: Ed25519 vs ML-DSA-65 (FIPS 204), 4 KiB message

| Algorithm | sign µs | verify µs | signature B | public key B |
|---|---:|---:|---:|---:|
| Ed25519 | 180.8 | 119.1 | 64 | 32 |
| ML-DSA-65 | 932.2 | 203.8 | 3309 | 1952 |

Model verification on load hashes the model files (SHA-256) and verifies one ML-DSA-65
signature over the manifest. That is about 0.2 ms plus hashing, once per model load. The
3.3 KB signature is irrelevant next to a model artifact.

## Verified behaviour (tests, not just numbers)

| Check | Result | Where |
|---|---|---|
| Hybrid-only server + hybrid client | handshake OK, group X25519MLKEM768 | `libs/ns-pqc/tests/test_pqc.py` (real sockets) |
| Hybrid-only server + classical-only client | refused | same, plus `GatewayLLM` against `llm_gateway.serve` |
| Hybrid-preferred / classical servers | probe reports "classical still accepted" / "classical only" | same |
| Untrusted CA | refused (CERTIFICATE_VERIFY_FAILED) | same |
| Signed model | `pass` | `test_pqc.py`, `services/ml-service/tests/test_model_signature.py` |
| Tampered file / extra file / missing file / edited card / edited manifest / other key | `fail`; ml-service returns 503 under `MODEL_VERIFY=enforce` | same, plus `.github/workflows/verify-model.yml` |

## Not covered (yet)

- Certificates are still ECDSA P-256 (authentication is not exposed to harvest-now-decrypt-later). ML-DSA certificates are a Phase 3 item.
- Only copilot → llm-gateway uses TLS. Other compose-network hops are plaintext, and the PQC panel lists them as such.
- Docker was not available on the dev box that produced these numbers. They come from the same OpenSSL 3.5 line the images use, and CI (`verify-model.yml`) reruns the checks inside `python:3.12-slim-trixie`.
