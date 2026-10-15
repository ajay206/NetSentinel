# ADR-019: Post-quantum TLS (hybrid ML-KEM) and ML-DSA model signing

- **Status:** Accepted (Step 21, W21). TelcoGPT-mini (W19–20) moved to the next phase, so this step does not depend on it.
- **Context:** Prompts and alarm data cross the network between the copilot and llm-gateway, and models are loaded from disk. Recorded traffic could be decrypted later by a quantum computer (harvest-now-decrypt-later), and a swapped model file would be served silently.

## Decision

1. **Hybrid key exchange from OpenSSL 3.5, no liboqs.** OpenSSL 3.5 implements ML-KEM (FIPS 203) and the `X25519MLKEM768` TLS group natively. Debian trixie ships it, so the affected images move from `python:3.12-slim` to `python:3.12-slim-trixie` (multi-arch, with a build-time assert of OpenSSL ≥ 3.5). The build plan's `liboqs` + `oqs-provider` is not needed. That drops a custom-compiled provider from every image.
2. **Policy via `OPENSSL_CONF`** (`infra/pqc/openssl-hybrid.cnf`: `Groups = X25519MLKEM768`). Python's `ssl` has no per-context group API in 3.12, and the system-default config applies to every TLS context in the process. llm-gateway is **hybrid-only**, so classical-only clients are refused. The copilot uses `openssl-hybrid-pref.cnf` (hybrid first, X25519 kept for external HTTPS such as Langfuse); against the hybrid-only gateway it always negotiates hybrid.
3. **Scope: copilot → llm-gateway first** (`https://llm-gateway:8443`). That hop carries the most sensitive text. Other compose hops stay plaintext on the internal network for now, and the status panel says so instead of over-claiming.
4. **Certificates:** a one-shot `pqc-init` container creates a dev CA and service certs (ECDSA P-256) plus the ML-DSA-65 model-signing keypair in the `pqc` volume. It is idempotent. Authentication is not exposed to HNDL, so ML-DSA certificates wait for Phase 3.
5. **ML-DSA-65 (FIPS 204) model signing** with `cryptography`'s ML-DSA, not the CLI. It works in any image. `ns_pqc.sign_dir` writes `signature.json`: SHA-256 of every file in the model version directory (+ optional model card) and the key id, signed over canonical JSON. `verify_dir` checks the key id, the signature, the exact file set and every digest.
6. **Verify on load:** ml-service checks the signature *before* loading the XGBoost model (`MODEL_VERIFY=off|warn|enforce`, compose: `enforce`). On failure it answers 503 and reports the result at `/model/signature`. In the dev stack the auto-trained model is signed with pqc-init's key; a real release is signed offline with `scripts/sign_model.py`, and only the public key is mounted.
7. **Status from reality:** api-gateway `GET /api/security/pqc` (viewer) runs real handshakes per policy (hybrid-only and classical-only, each in a child process) and reads the model verify result. The console **PQC status** panel shows exactly that.

## Consequences

- +0.12 ms and about 2 KB per full handshake (`docs/pqc_report.md`), which is negligible on a keep-alive connection in front of an LLM.
- One more volume and an init container. Private keys live only in the `pqc` volume or `.pqc/` (gitignored).
- `OPENSSL_CONF` is process-wide: a service that must also talk to classical-only peers uses the hybrid-preferred file, never the hybrid-only one.
- TelcoGPT-mini releases (Phase 3) reuse `scripts/sign_model.py` unchanged.
