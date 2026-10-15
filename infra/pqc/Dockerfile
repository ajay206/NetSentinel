# Step 21: one-shot PQC material (dev CA, service TLS certs, ML-DSA-65 model-signing key).
# Multi-arch: python:3.12-slim-trixie and the uv image publish linux/amd64 and linux/arm64.
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.12-slim-trixie

COPY --from=uv /uv /bin/uv
ENV UV_NO_CACHE=1 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY libs ./libs
COPY services ./services
RUN uv sync --frozen --no-dev --package ns-pqc
COPY scripts/pqc_init.py scripts/sign_model.py scripts/bench_tls.py ./scripts/
COPY infra/pqc ./infra/pqc
COPY infra/pqc/*.cnf /etc/netsentinel/pqc/

# /pqc is a named volume: created here so its first mount is owned by uid 1000 (all services)
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser && mkdir /pqc \
    && chown appuser /pqc
USER appuser
VOLUME /pqc

CMD ["python", "scripts/pqc_init.py", "--out", "/pqc", "--services", "llm-gateway"]
