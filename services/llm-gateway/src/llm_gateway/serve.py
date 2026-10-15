"""Container entrypoint: HTTPS (Step 21) when LLM_GATEWAY_TLS_CERT/KEY are set, else plain HTTP.

The key-exchange group (hybrid X25519MLKEM768) comes from OPENSSL_CONF, see infra/pqc/.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    cert, key = os.getenv("LLM_GATEWAY_TLS_CERT"), os.getenv("LLM_GATEWAY_TLS_KEY")
    port = int(os.getenv("PORT", "8443" if cert else "8010"))
    uvicorn.run(
        "llm_gateway.main:app",
        host="0.0.0.0",
        port=port,
        ssl_certfile=cert or None,
        ssl_keyfile=key or None,
        log_level="info",
    )


if __name__ == "__main__":
    main()
