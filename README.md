# OrkaFin Local V1

OrkaFin Local V1 is a reproducible, permission-aware guidance layer for the synthetic OrkaATS pilot. It is not a generic chatbot, candidate system of record, or production deployment. OrkaATS owns candidate data, permission decisions, business validation, and writes. OrkaFin never directly reads or writes the OrkaATS Google Sheet.

The local demo provides deterministic grounded answers, field-redacted candidate summaries, recommendations and feedback, append-only audits, and one separately confirmed mock-only start-date action. It works without an AI-provider key, network access, Apps Script, or live candidate data.

## Start the demo

Prerequisites: Python 3.11+, Node.js 18+ for the widget test, and `make` (optional). From a fresh clone:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp -n .env.example .env
python scripts/run_local_demo.py --subject admin
```

Open <http://127.0.0.1:8000/demo>. The demo launcher refuses non-local, non-SQLite, non-deterministic-provider, credentialed-CORS, non-loopback, and non-fixture configuration before it migrates or starts anything. It performs the local migration, validates checked-in knowledge, and resets only adapter-owned mock state.

Use `--check-only` to perform those checks without starting the server:

```bash
python scripts/run_local_demo.py --subject admin --check-only
```

The default `admin` fixture can use the mock action. Start with `--subject limited_viewer` to demonstrate field-redacted summaries and an unavailable action. All fixture data is synthetic.

## What to try

1. Keep **Candidate profile** and `CAND-1042`, open **Ask OrkaFin**, and ask **Explain this page** or **Summarize this candidate**. Responses show their approved sources; the candidate summary omits restricted/sensitive fields.
2. Ask **What is quantum candidate matching?** for the explicit unavailable response. Select `CAND-1099` and request a summary for a safe access denial.
3. Select **Recruitment pipeline** with no candidate to view the deterministic recommendation. Its controls submit helpful, not-helpful, accepted, dismissed, or disabled-preference feedback.
4. With the `admin` fixture on `CAND-1042`, preview a different start date, review it, confirm it, then use the separate execution click. This changes only `var/mock_orka_ats_state.json`.
5. Inspect bounded redacted local activity; no public audit API exists:

   ```bash
   python scripts/inspect_local_activity.py --limit 20
   ```

See [the walkthrough](docs/LOCAL_DEMO.md) for expected behavior and the optional action flow.

## Verification

The complete local release gate is:

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

The security suite blocks live sockets; the demo and tests do not contact an external provider, Apps Script, Google Sheet, or real candidate system. Results, coverage, residual risks, and the human sign-off record are in [the V1 acceptance checklist](docs/V1_ACCEPTANCE_CHECKLIST.md).

## Documentation map

- [Local setup](docs/LOCAL_SETUP.md) — reproducible install, configuration, and release commands.
- [Local demo](docs/LOCAL_DEMO.md) — browser/API walkthrough and expected results.
- [Developer runbook](docs/DEVELOPER_RUNBOOK.md) — resets, local inspection, and safe troubleshooting.
- [API](docs/API.md) — public V1 endpoints and synthetic examples.
- [Orka app onboarding guide](docs/ORKA_APP_ONBOARDING_GUIDE.md) — the general adapter path for a future app.
- [Future migration plan](docs/FUTURE_MIGRATION_PLAN.md) — gates for tunnels, hosted service, identity, and operations.
- [Test strategy](docs/TEST_STRATEGY.md) and [threat model](docs/THREAT_MODEL.md) — tested controls and residual risks.
- [Decisions](docs/DECISIONS.md) — frozen Local V1 boundaries and the human review record.

Before changing a trust boundary, candidate persistence, authentication method, adapter transport, action, browser origin, or deployment topology, update the affected decision/security documents and add or supersede an ADR. The final local acceptance does not approve any production boundary.
