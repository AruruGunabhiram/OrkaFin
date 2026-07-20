# Local V1 Final Acceptance Checklist

**Status:** Technical acceptance evidence is recorded below; final human acceptance is pending the project lead.

This checklist reports what the local deterministic repository exercised. It is not a claim of production readiness, compliance, or a completed penetration test. All IDs, names, fields, and URLs in examples are synthetic.

## Twenty Local V1 acceptance targets

| ID | Target | Local evidence | Status |
|---|---|---|---|
| A-01 | Fresh Python environment installs the package and dev tools | Clean run used `python3 -m venv .venv` and `python -m pip install -e '.[dev]'`; package/API tests passed | Pass |
| A-02 | Safe `.env` copy and fixture-only configuration | `cp -n .env.example .env`, launcher refusal tests, `run_local_demo.py --check-only` | Pass |
| A-03 | Alembic creates only OrkaFin-owned SQLite tables | clean migration, `test_fresh_migration_creates_only_approved_orkafin_tables` | Pass |
| A-04 | OrkaATS starter knowledge validates and loads | `python -m orkafin.knowledge.validate knowledge/orka_ats`, loader tests | Pass |
| A-05 | Mock OrkaATS state resets independently | seed command and mock state reset tests | Pass |
| A-06 | Loopback FastAPI serves health, demo HTML, and static widget | Local Uvicorn smoke returned health JSON and corrected `/demo` HTML; app/asset tests passed | Pass; visual browser smoke remains human follow-up |
| A-07 | Browser context is resolved from trusted identity, not forged client claims | context/identity security tests | Pass |
| A-08 | Page, feature, and help guidance is grounded in approved sources | retrieval, response, grounding, and E2E tests | Pass |
| A-09 | Candidate summaries are record/field permission safe and non-persistent | redaction, persistence, sensitive-boundary, and E2E tests | Pass |
| A-10 | Unknown, denied, offline, and adapter-failure paths remain honest | assistant/context/error/widget tests | Pass |
| A-11 | Basic deterministic recommendation is source-aware | recommendation API and E2E tests | Pass |
| A-12 | Helpful, not-helpful, accepted, dismissed, and opt-out feedback work | recommendation integration tests and widget feedback regression | Pass |
| A-13 | Local events are bounded and inspectable without a public endpoint | `inspect_local_activity.py` regression and read-only CLI | Pass |
| A-14 | Audits are append-only, minimized, and inspectable with redaction | audit tests, sensitive-boundary test, read-only CLI | Pass |
| A-15 | Optional action has preview, confirmation, revalidation, execution receipt, and idempotency | action integration/security tests and widget action tests | Pass |
| A-16 | Action conflicts/timeouts/malformed receipts never fabricate success | action execution/security/widget timeout tests | Pass |
| A-17 | No direct Google Sheet access or candidate persistence exists | adapter boundary tests, migration/schema inspection, architecture review | Pass |
| A-18 | Versioned errors, request IDs, and restrictive CORS are enforced | request-ID/error and CORS security tests | Pass |
| A-19 | Secret checks and no-live-network rule protect local QA | secret scan, repository scan test, global socket guard | Pass |
| A-20 | Full release gate, coverage threshold, and widget regression pass | Clean-state command output recorded below; 85.3% aggregate coverage exceeds 82.0% | Pass |

## Deliberately deferred features

| Deferred item | Status and reason |
|---|---|
| Live OrkaATS/Apps Script/Google Sheet data path | Not implemented; requires reviewed authenticated adapter topology and synthetic integration evidence first |
| Production OAuth or end-user identity | Not implemented; fixture subject is a local harness only |
| External AI provider in the demo | Not enabled; deterministic provider keeps setup offline and repeatable |
| Cloud/hosted API, managed database, or remote audit UI | Not implemented; deployment, retention, observability, and access controls are unresolved |
| More actions, autonomous execution, or background workers | Not implemented; one mock action is the bounded POC |
| Candidate cache, raw notes, document ingestion, or vector database | Not implemented; violates/expands the current ownership and retrieval boundary |
| Production performance/load, multi-process race, accessibility, or browser compatibility certification | Not claimed; manual and future reviewed testing remains necessary |

## Final clean-state verification record

Run from a fresh local environment:

```bash
rm -rf .venv var/orkafin.db
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp -n .env.example .env
alembic upgrade head
python -m orkafin.knowledge.validate knowledge/orka_ats
python -m orkafin.adapters.orka_ats.seed --reset
python scripts/run_local_demo.py --subject admin --check-only
ruff format --check .
ruff check .
mypy src
pytest --cov=orkafin --cov-report=term-missing -q
node --test tests/web/widget.test.mjs
python scripts/scan_secrets.py
```

Observed on 2026-07-19 (America/Denver), using Python 3.14.4:

| Command | Result |
|---|---|
| `python3 -m venv .venv` | Pass. Bare `python` was not installed before activation, so the portable setup command uses `python3`; activated `.venv` provides `python`. |
| `python -m pip install -e '.[dev]'` | Pass from the newly created environment. |
| `alembic upgrade head` | Pass; applied four revisions through `c19e2a4b7d01`. |
| `python -m orkafin.knowledge.validate knowledge/orka_ats` | Pass; 1 action, 5 features, 6 help articles, 6 pages, 4 permissions, and 1 recommendation. |
| `python -m orkafin.adapters.orka_ats.seed --reset` | Pass; reset isolated `var/mock_orka_ats_state.json`. |
| `python scripts/run_local_demo.py --subject admin --check-only` | Pass; 6 pages, 5 features, 6 help articles, mock state reset. |
| Local Uvicorn smoke | Pass; `/health` returned `{"status":"ok","service":"orkafin","version":"v1"}`, `/demo` served valid synthetic controls, and a loopback API flow exercised grounded, redacted, unavailable, recommendation/feedback, and mock action outcomes. |
| `ruff format --check .` / `ruff check .` | Pass; 149 files formatted and lint clean. |
| `mypy src` | Pass; no issues in 91 source files. |
| `pytest --cov=orkafin --cov-report=term-missing -q` | Pass; 249 passed, 85.34% aggregate coverage (89.3% statements, 66.7% branches), above the 82.0% threshold. |
| `node --test tests/web/widget.test.mjs` | Pass; 7 tests passed. |
| `python scripts/scan_secrets.py` | Pass; 220 tracked/non-ignored repository files checked. |

`uvicorn orkafin.main:app --reload` and the manual browser flow remain a short-lived local smoke, not a production deployment test. The in-app browser automation connection was unavailable in this environment, so the final human reviewer must perform the visual/focus/offline widget checklist in `LOCAL_SETUP.md`.

## Required human acceptance

| Field | Value |
|---|---|
| Project lead | Pending |
| Review date | Pending |
| Local technical evidence reviewed | Pending |
| Optional mock action accepted as mock-only | Pending |
| Deferred production work accepted | Pending |
| Outcome | Pending: approve, approve with conditions, or request changes |
| Conditions / V2 backlog owner | Pending |

Until this record is approved, Local V1 remains a developer handoff with technical evidence rather than final human acceptance.
