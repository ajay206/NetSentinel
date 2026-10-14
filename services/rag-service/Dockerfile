FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY libs ./libs
COPY services ./services
COPY data/runbooks ./data/runbooks
RUN uv sync --frozen --no-dev --package rag-service
RUN useradd --no-create-home --shell /bin/bash appuser
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8004
CMD ["uv", "run", "--no-sync", "uvicorn", "rag_service.api:app", "--host", "0.0.0.0", "--port", "8004"]
