# Build stage
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv

# Runtime stage
FROM python:3.12-slim

# Install uv
COPY --from=uv /uv /bin/uv

# Set working directory
WORKDIR /app

# Copy workspace files
COPY pyproject.toml uv.lock README.md ./
# Every workspace member must be present for `uv sync --frozen`
COPY libs ./libs
COPY services ./services

# Install dependencies (production only)
RUN uv sync --frozen --no-dev --package api-gateway

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# Set PATH to include uv-installed packages
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
