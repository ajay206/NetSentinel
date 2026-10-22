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
6. `console` job (only when `apps/noc-console/**` changes): `npm ci`, lint, typecheck, Vitest, build.
7. `layout-audit` job (after `console`, same path filter plus `ci.yml`): installs Chromium, starts Vite on `127.0.0.1:5179` and runs `LAYOUT_STRICT=1 npx playwright test e2e/layout-audit.spec.ts` with mocked APIs at 375 / 768 / 1280 / 1440 px. It fails on sideways page scroll, elements spilling out of cards, or truncated text without a `title`. Screenshots are uploaded as the `layout-audit` artifact only when it fails.
   Run it locally: `cd apps/noc-console && npx vite --port 5179 --strictPort & LAYOUT_STRICT=1 npx playwright test e2e/layout-audit.spec.ts`.

## verify-model workflow (Step 21, `.github/workflows/verify-model.yml`)

This workflow runs inside the `python:3.12-slim-trixie` container (the service base image, OpenSSL 3.5). It:

- asserts that OpenSSL has ML-KEM / ML-DSA;
- trains a tiny fault classifier, signs it and its model card with ML-DSA-65 and verifies it, then appends one byte and requires verification to **fail**;
- runs the PQC tests: real hybrid / classical handshakes against hybrid-only, hybrid-preferred and classical servers, an untrusted CA, ml-service verify-on-load (enforce → 503) and the status aggregation;
- runs a 100-round benchmark smoke.

The handshake tests skip themselves on hosts with OpenSSL < 3.5; in this workflow they always run.

