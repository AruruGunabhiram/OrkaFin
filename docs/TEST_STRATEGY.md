# OrkaFin Test Strategy

## Local V1 checks

Every implementation increment runs the database migration, controlled knowledge
validation, formatter/linter, type checker, and pytest suite. Tests use synthetic
adapter fixtures and temporary SQLite databases; they require no external model
provider or OrkaATS spreadsheet access.

```bash
alembic upgrade head
python -m orkafin.knowledge.validate knowledge/orka_ats
ruff format --check .
ruff check .
mypy src
pytest -q
```

## Prompt 17 coverage

`tests/integration/test_recommendations_events_feedback_api.py` verifies the
source-backed `review_recruitment_pipeline` rule, deterministic feature/source
selection, trusted permission/page filtering, one-impression frequency limiting,
dismissal and acceptance suppression, `disabled` preference behavior, all four
feedback types, event allowlisting, metadata bounds, and email/PII exclusion.

Knowledge loader tests reject unknown rule references. Existing persistence tests
exercise the migration and table constraints. Widget static tests ensure the
framework-free assets never include credentials or browser permission claims; the
recommendation card is deliberately rendered only inside the panel and does not
re-open it after a context change.
