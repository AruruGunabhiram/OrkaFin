# Local Development Setup

## Prerequisites

- Python 3.11 or newer. The project targets Python 3.11 language semantics and
  was verified with the local Python interpreter recorded in the handoff.
- `make` (optional; every command has a direct equivalent below).

## Fresh-clone setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
```

The service reads `.env` through Pydantic Settings with the `ORKAFIN_` prefix. No
external key is required when `ORKAFIN_AI_PROVIDER=deterministic`.

## Development commands

```bash
make format
make lint
make typecheck
make test
make migrate
make knowledge-validate
make run
```

Direct equivalents are `ruff format .`, `ruff check .`, `mypy src`, `pytest -q`,
`alembic upgrade head`, `python scripts/validate_knowledge.py`, and
`uvicorn orkafin.main:app --reload`.

The migration command creates or upgrades `var/orkafin.db` through Alembic's
initial OrkaFin-owned schema. `make database-init` is an alias for this local
initialization. It never creates a candidate table or copies OrkaATS records. The
knowledge command only verifies the reserved `knowledge/orka_ats` directory; it
does not load or interpret knowledge content.

## Run and verify

Start the service with `make run`, then request:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","service":"orkafin","version":"v1"}
```

## Local assistant widget demo

The reusable, framework-free widget is served at
`http://127.0.0.1:8000/demo`. It uses the same origin as the API, so the default
loopback CORS policy is sufficient for the demo. It is a synthetic local harness,
not an Apps Script deployment.

The API fails closed unless a trusted session resolver is configured. To run the
interactive synthetic fixture harness, set the fixture subject on the **server**
when starting it (the browser never supplies identity, role, permissions, or a
secret):

```bash
python -m orkafin.adapters.orka_ats.seed --reset
ORKAFIN_LOCAL_FIXTURE_SUBJECT=admin uvicorn orkafin.main:app --reload
```

Then open `http://127.0.0.1:8000/demo`. Choose a page and synthetic candidate,
open **Ask OrkaFin**, and use a suggested prompt or enter a question. `CAND-1099`
is intentionally useful for checking a safe denied response. Valid synthetic
fixture subjects are defined in `fixtures/orka_ats/users.yaml`; the local demo does not
provide a browser identity switcher.

The `admin` fixture is required for the one mock action. Preview a new start date,
confirm it, and then click **Execute approved update** separately. Success changes
only isolated mock adapter state. It does not contact Apps Script or a Google
Sheet. Reset that state with the seed command before repeating the demo.

Manual smoke checklist:

1. Confirm the panel can be opened with the launcher and closed with Escape.
2. Select `Candidate profile` and `CAND-1042`, then send **Summarize this candidate**.
3. Confirm sources and the request ID render when the response provides them.
4. Select `CAND-1099` and confirm denial is displayed without a fabricated summary.
5. Stop the local service, submit a question, and confirm the offline message; restart it.
6. Use **Reset conversation** and verify the response area returns to its empty state.
7. Preview and confirm a different `CAND-1042` start date; verify no value changes
   before the separate execution click.
8. Execute once, verify the adapter-confirmed success, and resolve the candidate
   context again to see the synthetic value.

For the lightweight frontend checks, run:

```bash
node --test tests/web/widget.test.mjs
```

## Dependency policy

`pyproject.toml` is the single dependency and tooling configuration source.
Dependencies use bounded compatible ranges: FastAPI/Pydantic/SQLAlchemy/Alembic
remain below their next major version, while development tools remain below their
next planned breaking major. Installation resolves concrete versions appropriate
to the current Python interpreter.

## Reserved environment variables

`.env.example` records the supported names and safe local examples:

- `ORKAFIN_ENVIRONMENT`
- `ORKAFIN_DATABASE_URL`
- `ORKAFIN_LOG_LEVEL`
- `ORKAFIN_ALLOWED_ORIGINS`
- `ORKAFIN_CORS_ALLOW_CREDENTIALS`
- `ORKAFIN_ACCEPT_INCOMING_REQUEST_IDS`
- `ORKAFIN_AI_PROVIDER`
- `ORKAFIN_AI_PROVIDER_API_KEY`
- `ORKAFIN_CONFIRMATION_TTL_SECONDS`
- `ORKAFIN_FIXTURE_MODE`
- `ORKAFIN_LOCAL_FIXTURE_SUBJECT`
- `ORKAFIN_DEBUG`

Never commit `.env` or real provider credentials. Browser-provided identity and
authorization values remain untrusted regardless of local configuration.

`ORKAFIN_ALLOWED_ORIGINS` is a comma-separated, loopback-only allowlist.
Credentialed wildcard CORS, non-SQLite database URLs, production environment
mode, debug outside development, and an external provider without an API key are
rejected during application construction. Debug mode never includes secrets or
tracebacks in API responses.

Every response includes an `X-Request-ID` header. The server accepts only a
canonical UUID request ID from that header when
`ORKAFIN_ACCEPT_INCOMING_REQUEST_IDS=true`; other values are replaced with a new
UUID. Errors use the versioned `ApiError` JSON envelope and include the same ID.
