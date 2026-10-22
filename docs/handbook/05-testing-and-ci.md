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


## W24: path-filtered CI, eval gate, images, retraining

- **`ci.yml`** starts with a `changes` job (dorny/paths-filter). `python` runs for services, libs, scripts, evals, docs and lock changes. `console` and `layout-audit` run for `apps/noc-console/**`. `eval-gate` runs for ml-service and evals changes. `helm` (lint + kubeconform) runs for `deploy/**`. Every job also runs when `ci.yml` itself changes. Skipped jobs count as passed.
- **Eval gate** (`evals/gate.py`, `ml_service/gate.py`):
  - It retrains the fault classifier, loads `model.json` and re-scores it on an independent synthetic hold-out (seed 9001). It never trusts `meta.json`.
  - It blocks when accuracy or macro-F1 is below 0.80, any class F1 is below 0.60, or macro-F1 falls more than 0.03 below the champion in `evals/gate_thresholds.json`.
  - CI also trains a deliberately degraded model (shuffled labels) and fails if that one passes.
  - Results go to the sidecar `<version>.gate.json`, outside the signed file set.
  - To try it locally: `uv run python evals/gate.py --train` (passes) and `--train --degrade` (blocked, exit 1).
- **Drift:** `evals/drift_check.py` computes PSI per feature. Above 0.1 is a warning, above 0.2 is drift (exit 1). `--shift 1.5` demonstrates an alert.
- **`images.yml`** builds all 13 images. PRs build only. Pushes to `main` and `v*` tags push `ghcr.io/<owner>/netsentinel-<svc>:{sha,latest,tag}` with `GITHUB_TOKEN` (no extra secrets).
- **`retrain.yml`** runs Mondays at 09:00 IST, or by hand with `gh workflow run retrain.yml -f promote=true`. The steps are: train, sign with ML-DSA-65 (ephemeral CI key), verify, gate, drift, then `scripts/mlflow_promote.py`.
  - The promote step registers `netsentinel-fault-classifier` and moves the `champion` alias only if the gate passed.
  - Without the `MLFLOW_TRACKING_URI` repo secret it's a dry run.
  - The model, gate result and drift report are uploaded as artifacts.
- **`verify-model.yml`** (Step 21) still runs on every push/PR: sign, verify, tamper must fail.
- **Console:** Service health shows a `model <version> · gate pass|blocked|not gated` chip from `GET /api/ml/model/info`. "Not gated" is the dev model auto-trained at start-up.
- **Governance:** `docs/risk_register.md`, `docs/data_contract.md` and `docs/stakeholder_onepager.md`.
