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

The scaffold does not read `.env` yet. Its documented names reserve the explicit
configuration contract for Prompt 3; no external key is required for the service
to start.

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

`.env.example` records the names and safe local examples planned for Prompt 3:

- `ORKAFIN_ENVIRONMENT`
- `ORKAFIN_DATABASE_URL`
- `ORKAFIN_LOG_LEVEL`
- `ORKAFIN_ALLOWED_ORIGINS`
- `ORKAFIN_AI_PROVIDER`
- `ORKAFIN_AI_PROVIDER_API_KEY`
- `ORKAFIN_CONFIRMATION_TTL_SECONDS`
- `ORKAFIN_FIXTURE_MODE`

Never commit `.env` or real provider credentials. Browser-provided identity and
authorization values remain untrusted regardless of local configuration.
