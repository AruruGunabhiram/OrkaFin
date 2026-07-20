# OrkaFin Test Strategy

## Local V1 checks

Every implementation increment runs the database migration, controlled knowledge
validation, formatter/linter, type checker, and pytest suite. Tests use synthetic
adapter fixtures and temporary SQLite databases; they require no external model
provider or OrkaATS spreadsheet access.

```bash
python -m orkafin.adapters.orka_ats.seed --reset
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

## Prompt 19 action execution matrix

Prompt 18 preparation coverage remains: exact catalog allowlisting, missing
permission, invisible candidate, malformed/no-op date, adapter outage, preview
content, hash-only token persistence, parameter/token tampering, expiry, replay,
wrong user/workspace, cancellation, audits, and conditional state transitions.

`tests/integration/test_action_execution_api.py` adds:

- adapter-receipt-confirmed success and persisted mock-state visibility;
- action-permission and candidate-visibility revocation after confirmation,
  including terminal one-time confirmation consumption without adapter dispatch;
- candidate-state change between confirmation and execution;
- accepted-confirmation expiry, parameter-hash tampering, and action-version drift;
- explicit adapter validation failure;
- timeout and unavailable outcomes that remain `unknown` and never assert no
  change;
- a mismatched receipt after a real mock effect, proving success is not
  fabricated;
- duplicate endpoint execution, confirmation reuse, one execution row, one mock
  receipt, and one adapter-request audit; and
- the complete attempt, execution permission, adapter request, outcome, and final
  safe-result audit sequence.

Each execution test injects a temporary mock-state path and resets it first. The
success test verifies only the adapter-owned JSON state changes; OrkaFin still has
no candidate table. Reset and state-store tests restore baseline values and clear
receipts. Contract tests retain request/receipt structural invariants and adapter
capability checks.

Framework-free widget tests require three distinct user phases: preview, confirm,
and a separate execution click. They verify the plaintext challenge never renders,
success uses adapter-confirmed text, and client timeout/offline errors remove the
execution control and use reconciliation-safe wording without “no changes.”

Full Prompt 19 verification runs the reset, migrations, catalog validation, Ruff,
mypy, complete pytest suite, Node widget suite, and a local HTTP action demo. No
test contacts an external model, Apps Script deployment, Google Sheet, or real
candidate system.
