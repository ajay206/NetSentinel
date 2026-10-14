# 06 - Troubleshooting

## Common Issues & Solutions

### 1. Docker Compose fails to start TimescaleDB (`POSTGRES_PASSWORD` error)
* **Cause:** The `.env` file is missing or `POSTGRES_PASSWORD` is not set.
* **Solution:** Run `cp .env.example .env` and populate `POSTGRES_PASSWORD=your_password`.

### 2. Kafka container exits or unhealthy
* **Cause:** Insufficient Docker memory allocation or port conflict on 9092.
* **Solution:** Ensure Docker Desktop has at least 4 GB RAM allocated. Check port availability (`lsof -i :9092`).

### 3. `uv sync` fails building `confluent-kafka` (`librdkafka/rdkafka.h` not found)
* **Cause:** `uv` picked Homebrew Python 3.15. There is no binary wheel, so it compiles C code and needs librdkafka headers.
* **Solution:** Use 3.12 (repo pins `.python-version`). Remove the 3.15 venv and re-sync:
  ```bash
  source $HOME/.local/bin/env
  rm -rf .venv
  uv python install 3.12
  uv sync --all-extras --dev --python 3.12
  ```
  Do not `brew install librdkafka` unless you intentionally want to compile against 3.15.

### 4. `uv sync` or workspace package resolution issues
* **Cause:** Outdated `uv` version or uninitialized workspace members.
* **Solution:** Upgrade `uv` and re-run `uv sync --all-extras --dev --python 3.12`.

### 5. Docker: `Cannot connect to the Docker daemon` / `docker info` has Client but Server fails
* **Cause:** Docker CLI is installed; the Docker Desktop **engine** is not running (`docker.sock` missing).
* **Solution:** Open Docker Desktop from Applications and wait until it is idle. Confirm with `docker info` showing a **Server** section (not only Client). Then `make up-core`.

### 6. Ruff or pre-commit hook failures
* **Cause:** Code formatting or linting rules violated.
* **Solution:** Run `make fmt` (`uv run ruff format .`) and `make lint` (`uv run ruff check .`) to automatically fix and check issues.
