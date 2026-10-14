FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY libs ./libs
COPY services ./services
RUN uv sync --frozen --no-dev --package copilot-orchestrator
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8005
CMD ["uv", "run", "--no-sync", "uvicorn", "copilot_orchestrator.api:app", "--host", "0.0.0.0", "--port", "8005"]
