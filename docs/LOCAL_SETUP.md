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

The migration command initializes Alembic's empty migration state only. Prompt 2
creates no SQLAlchemy models or candidate-related tables. The knowledge command
only verifies the reserved `knowledge/orka_ats` directory; it does not load or
interpret knowledge content.

## Run and verify

Start the service with `make run`, then request:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","service":"orkafin","version":"v1"}
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
