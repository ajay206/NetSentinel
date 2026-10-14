# 05 - Testing & CI/CD

## Testing Strategy
* **Unit Tests:** Written using `pytest` located in `libs/*/tests/` and `services/*/tests/`. alarm-ingest tests (W4) run with `DISABLE_KAFKA=1` and a fake clock for dedup/correlation windows: `uv run pytest services/alarm-ingest -v`.
* **Console tests:** Vitest (`make console-test`); W4 adds `EnrichedAlarms.test.tsx` and `applyEnrichedMessage.test.ts`.
* **Linting & Formatting:** Enforced via `ruff` (`line-length = 100`, select `E, F, I, B, UP`).
* **Pre-commit Hooks:** Enforce formatting, trailing whitespace fixes, and lint checks prior to commit (`uv run pre-commit install`).

## CI Pipeline (`.github/workflows/ci.yml`)
The GitHub Actions CI pipeline automatically runs on every push and pull request:
1. Sets up Python 3.12 and `astral-sh/setup-uv`.
2. Runs `uv sync --all-extras --dev`.
3. Runs `uv run ruff check .` (Linter).
4. Runs `uv run ruff format --check .` (Formatter check).
5. Runs `uv run pytest` (Test suite).
