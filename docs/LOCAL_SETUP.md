# Local Development Setup

This is the proven path for a new developer to run Local V1. It uses only checked-in synthetic fixtures. It does not authenticate a real user or connect to OrkaATS, Apps Script, a Google Sheet, or an AI provider.

## Prerequisites

- Python 3.11 or newer.
- Node.js 18 or newer for `node --test tests/web/widget.test.mjs`.
- `make` is optional; direct commands are shown below.

## Fresh-clone installation

```bash
git clone <repository-url>
cd Orka_Fin_V1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp -n .env.example .env
```

`cp -n` creates `.env` only when one is absent, so it cannot overwrite a local configuration. `.env.example` contains safe local values: SQLite at `var/orkafin.db`, deterministic responses, credential-free loopback CORS, and no fixture subject. Do not put a real provider key in `.env` for this demo.

## Initialize and validate Local V1

Run these commands from the repository root with the virtual environment active:

```bash
alembic upgrade head
python -m orkafin.knowledge.validate knowledge/orka_ats
python -m orkafin.adapters.orka_ats.seed --reset
```

Alembic creates only OrkaFin-owned tables in `var/orkafin.db`; it never creates a candidate table. Knowledge is version-controlled and validated in place rather than loaded into a candidate store. The seed command resets only `var/mock_orka_ats_state.json`, which is adapter-owned mock action state.

The checked launcher performs the same three steps and verifies that its configuration remains fixture-only and loopback-only:

```bash
python scripts/run_local_demo.py --subject admin --check-only
```

Expected successful summary:

```text
Local demo checks passed: 6 pages, 5 features, 6 help articles; mock state reset at var/mock_orka_ats_state.json.
```

## Start FastAPI and the widget

The shortest safe command both prepares and starts the demo:

```bash
python scripts/run_local_demo.py --subject admin
```

Open <http://127.0.0.1:8000/demo>. The launcher uses `127.0.0.1` by default and refuses `0.0.0.0`, a non-SQLite path, fixture mode off, a configured provider key, an external provider, credentialed CORS, an unknown subject, or a non-local environment. Add `--reload` only for local code iteration.

For direct FastAPI startup, set the server-only fixture subject in the shell; the browser never supplies it:

```bash
ORKAFIN_LOCAL_FIXTURE_SUBJECT=admin uvicorn orkafin.main:app --reload
```

Then verify the process:

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status":"ok","service":"orkafin","version":"v1"}
```

Valid synthetic subjects are `admin`, `recruiter`, and `limited_viewer`. `admin` is the only fixture that receives the mock action. `unverified` and unknown subjects fail closed and are deliberately rejected by the launcher.

## Manual browser smoke

1. Open the panel with **Ask OrkaFin** and close it with Escape.
2. On **Candidate profile** with `CAND-1042`, ask a page, feature, or help question and verify the response lists approved sources.
3. Request **Summarize this candidate**. With `limited_viewer`, only name, recruiter, and stage are visible; email, dates, resume reference, and notes remain absent.
4. Select `CAND-1099` and request a summary. Confirm a safe denial rather than a fabricated summary or a record-existence explanation.
5. Ask **What is quantum candidate matching?** and confirm the explicit unavailable answer. Stop the server once and submit a question to verify the widget's offline message; restart it afterwards.
6. Select **Recruitment pipeline** and no candidate. Verify the recommendation, source references, and helpful/not-helpful/accept/dismiss controls. The **Disable recommendations** control persists a local preference.
7. As `admin` on `CAND-1042`, preview a different start date, confirm it, then click **Execute approved update** separately. Re-open the context to observe the synthetic state change. Reset it with the seed command before another run.
8. Use **Reset conversation**; it clears the widget's local conversation reference but does not erase append-only audit records.

## Inspect local events and audits

There is no public audit-read route. Use the local, read-only CLI instead:

```bash
python scripts/inspect_local_activity.py --kind all --limit 20
```

It accepts only an existing regular SQLite file, opens it in SQLite read-only mode, emits at most 200 rows per kind, redacts recognized credentials/emails and sensitive keys, and makes no HTTP request. Example shape:

```json
{
  "audits": [{"event_type": "candidate_read", "outcome": "allowed", "details": {"redacted_field_count": 5}}],
  "database": "var/orkafin.db",
  "events": [{"event_type": "assistant_query_submitted", "metadata": {}}]
}
```

## Development and release commands

```bash
ruff format .
ruff check .
mypy src
pytest -q
node --test tests/web/widget.test.mjs
```

The full release gate, including clean local state and coverage, is:

```bash
rm -f var/orkafin.db
python -m orkafin.adapters.orka_ats.seed --reset
alembic upgrade head
python -m orkafin.knowledge.validate knowledge/orka_ats
python scripts/scan_secrets.py
ruff format --check .
ruff check .
mypy src
pytest --cov=orkafin --cov-report=term-missing -q
node --test tests/web/widget.test.mjs
```

`scripts/scan_secrets.py` scans current tracked/non-ignored files without printing matched values. No dependency vulnerability scanner is configured; `docs/TEST_STRATEGY.md` records the recommended `pip-audit` commands and why no result is claimed.

## Supported local configuration

The supported environment variables and defaults are in `.env.example`. The important invariants are:

- `ORKAFIN_ENVIRONMENT=local`
- `ORKAFIN_DATABASE_URL=sqlite:///./var/orkafin.db`
- `ORKAFIN_AI_PROVIDER=deterministic`
- `ORKAFIN_FIXTURE_MODE=true`
- loopback-only origins and `ORKAFIN_CORS_ALLOW_CREDENTIALS=false`

`ORKAFIN_LOCAL_FIXTURE_SUBJECT` is blank by default so direct startup fails closed until the server operator supplies it. It is not browser authentication. The launcher supplies it only to its own local process after validating the synthetic subject.

For troubleshooting, fixture resets, action reconciliation, and safe failure behavior, see [the developer runbook](DEVELOPER_RUNBOOK.md). For all limits before live data or hosting, see [the future migration plan](FUTURE_MIGRATION_PLAN.md).
