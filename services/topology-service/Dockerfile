# Multi-arch: python:3.12-slim and the uv image both publish linux/amd64 and linux/arm64.
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /bin/uv

# uv is only used at build time; never let it touch a cache in $HOME at runtime.
ENV UV_NO_CACHE=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
# Every workspace member must be present for `uv sync --frozen`
COPY libs ./libs
COPY services ./services
# runbook metadata loaded on start (the topology is generated from TOPOLOGY_SEED by netgen)
COPY data/runbooks ./data/runbooks

RUN uv sync --frozen --no-dev --package topology-service

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser
USER appuser
ENV HOME=/home/appuser

EXPOSE 8008

# The venv is on PATH: run the server directly (no `uv run`, which needs a writable
# cache dir in $HOME and fails for a home-less non-root user).
CMD ["uvicorn", "topology_service.main:app", "--host", "0.0.0.0", "--port", "8008"]
