# NetSentinel CLI tools image: netgen-sim, the smoke test and gateway helpers, so the host needs
# only Docker + make + git. Used via `docker compose --profile cli run --rm tools <cmd>`.
# Multi-arch: python:3.12-slim and the uv image publish linux/amd64 and linux/arm64.
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /bin/uv

ENV UV_NO_CACHE=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY libs ./libs
COPY services ./services

# netgen-simulator: netgen-sim CLI; api-gateway: brings httpx for scripts/smoke.py
RUN uv sync --frozen --no-dev --package netgen-simulator --package api-gateway

COPY scripts ./scripts

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser
USER appuser
ENV HOME=/home/appuser

CMD ["python", "scripts/gw.py", "--help"]
