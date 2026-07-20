# Developer Runbook

This runbook is for the Local V1 operator. It handles only synthetic local state. It does not authorize access to real OrkaATS data or turn the mock adapter into a live integration.

## Normal local start

```bash
source .venv/bin/activate
python scripts/run_local_demo.py --subject admin
```

The launcher verifies local mode, deterministic generation, credential-free loopback CORS, the fixed local SQLite URL, fixture mode, a known synthetic user, and a loopback host. It then runs migrations, validates the knowledge catalog, resets mock adapter state, and starts FastAPI at `http://127.0.0.1:8000/demo`.

Use `--check-only` for a preflight. Use `--subject limited_viewer` to reproduce redaction and denied-action behavior. Use `--reload` only while editing local source files.

## Reset scopes

| Need | Command | What changes |
|---|---|---|
| Reset mock action value/receipts | `python -m orkafin.adapters.orka_ats.seed --reset` | Only `var/mock_orka_ats_state.json` |
| Recreate OrkaFin local records | `rm -f var/orkafin.db` then `alembic upgrade head` | Only OrkaFin-owned SQLite records |
| Reset both before a demo | `python scripts/run_local_demo.py --subject admin --check-only` after removing `var/orkafin.db` if desired | Database migration plus mock state reset |
| Validate catalogs without changing state | `python -m orkafin.knowledge.validate knowledge/orka_ats` | Nothing |

Do not delete fixture YAML files to reset a demo. They are version-controlled source data. Do not use a reset command against an OrkaATS database or Google Sheet; Local V1 has no such command.

## Read local activity safely

There is deliberately no public event or audit browsing endpoint. Inspect local data from the operator shell:

```bash
python scripts/inspect_local_activity.py --kind all --limit 50
python scripts/inspect_local_activity.py --kind audits --limit 20
python scripts/inspect_local_activity.py --kind events --limit 20
```

The command opens an existing SQLite file in read-only/query-only mode, bounds output to 200 rows per kind, and applies the same sensitive-content/key redaction policy used for logging. It cannot alter rows and never starts an HTTP route. Treat the resulting local file output as confidential operational material even though the fixtures are synthetic.

## Optional mock action walkthrough

The action exists only when all of these are true:

- server was started with synthetic `admin`;
- page is `candidate_profile`;
- selected candidate is currently visible to that fixture; and
- a different valid ISO date is previewed before the five-minute confirmation expires.

The UI sequence is preview → review exact values → confirm → separate execute. A confirmation never writes. An execution success is valid only after the mock adapter returns a matching receipt; ambiguous results are `unknown` and must not be retried from the UI.

For local mock reconciliation, inspect `var/mock_orka_ats_state.json` and the redacted audit CLI output by the recorded request/idempotency key. Reset mock state before repeating a manual demo. Never copy this workflow to a live system without the migration gates in [the future migration plan](FUTURE_MIGRATION_PLAN.md).

## Common local failures

| Symptom | Likely cause | Safe next step |
|---|---|---|
| Launcher says it refuses configuration | `.env` selects a non-local mode, external provider/key, non-SQLite database, credentialed CORS, non-loopback host, or unknown subject | Restore the safe values from `.env.example`; do not loosen the launcher checks |
| `identity_unverified` | Direct server start omitted `ORKAFIN_LOCAL_FIXTURE_SUBJECT` | Restart only the local process with a documented synthetic subject |
| `candidate_access_denied` | Selected candidate is private, archived, missing, or outside fixture grants | Use `CAND-1042` or test the denial intentionally; do not add a browser permission claim |
| `adapter_unavailable` | A mock/test failure simulation or unavailable local dependency was injected | Inspect request ID and redacted audit output; the UI must not invent a result |
| `action_state_conflict` | Current synthetic start date changed after preview or an execution already reserved it | Re-resolve context and prepare a new preview; reset mock state only for a local demo |
| `unknown` action result | Adapter confirmation was ambiguous/malformed | Do not retry; reconcile by idempotency key with the owning adapter in a future reviewed implementation |
| Widget says offline | Local FastAPI is stopped or wrong port/origin is open | Restart the checked launcher and use the same loopback URL |

## Release procedure

Run the commands in [Local setup](LOCAL_SETUP.md#development-and-release-commands) from a clean local database and reset mock state. The release gate includes knowledge validation, secret scanning, formatting, linting, typing, full Python coverage, and Node widget tests. Record failures rather than weakening tests or changing a boundary to make them pass.

The existing safety suite forbids live sockets in pytest. Never bypass it for an external provider or Apps Script test; a reviewed transport, fixture, and migration design are required first.

## Escalation boundaries

Stop and obtain human review before any action that would:

- supply real candidate data, production identity, provider credentials, or a live Apps Script endpoint;
- expose the local server beyond loopback, enable credentialed CORS, or add a public audit browser;
- add a candidate cache/table, direct Google Sheet access, or a new action; or
- select hosting, managed data storage, background processing, or production observability.

These are architecture changes, not routine operational fixes. See [Decisions](DECISIONS.md), [Security model](SECURITY_MODEL.md), and [Future migration plan](FUTURE_MIGRATION_PLAN.md).
