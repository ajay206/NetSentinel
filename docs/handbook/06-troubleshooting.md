# 06 - Troubleshooting

## Common Issues & Solutions

### 1. Docker Compose fails to start TimescaleDB (`POSTGRES_PASSWORD` error)
* **Cause:** The `.env` file is missing or `POSTGRES_PASSWORD` is not set.
* **Solution:** Run `cp .env.example .env` and populate `POSTGRES_PASSWORD=your_password`.

### 2. Kafka container exits or unhealthy
* **Cause:** Insufficient Docker memory allocation or port conflict on 9092.
* **Solution:** Ensure Docker Desktop has at least 4 GB RAM allocated. Check port availability (`lsof -i :9092`).

### 3. `uv sync` or workspace package resolution issues
* **Cause:** Outdated `uv` version or uninitialized workspace members.
* **Solution:** Upgrade `uv` (`pip install --upgrade uv`) and re-run `uv sync --all-extras --dev`.

### 4. Ruff or pre-commit hook failures
* **Cause:** Code formatting or linting rules violated.
* **Solution:** Run `make fmt` (`uv run ruff format .`) and `make lint` (`uv run ruff check .`) to automatically fix and check issues.
