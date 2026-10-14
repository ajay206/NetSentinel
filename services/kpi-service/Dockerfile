FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY libs ./libs
COPY services ./services

RUN uv sync --frozen --no-dev --package kpi-service

RUN useradd --create-home --shell /bin/bash appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8002

CMD ["uv", "run", "--no-sync", "uvicorn", "kpi_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
