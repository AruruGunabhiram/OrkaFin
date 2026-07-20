# OrkaFin Local V1 Test Strategy

**Status:** Prompt 20 security and regression gate; the optional single mock action is included.

This strategy verifies the documented Local V1 boundaries with synthetic data and
offline dependencies. It is not a penetration test, compliance assessment,
production-readiness claim, or proof about a live OrkaATS or AI-provider integration.

## Test pyramid and responsibilities

| Layer | Responsibility | Primary locations |
|---|---|---|
| Unit | Strict domain/config validation, permission and redaction invariants, deterministic retrieval/generation, catalog loading, logging, and static web assets | `tests/unit/` |
| Contract | The versioned adapter request/response contract, capability checks, typed failure mapping, receipt shape, and injected transport behavior | `tests/contracts/`, `tests/unit/test_adapter_contract.py`, `tests/unit/test_apps_script_adapter.py` |
| Security | Threat-oriented abuse cases that must fail closed across identity, record, provider, prompt, CORS, confirmation, network, and secret boundaries | `tests/security/` |
| Integration | FastAPI, application services, SQLite, audits, mock adapter state, errors, conversations, recommendations, and actions working together | `tests/integration/` |
| E2E | A deterministic health → metadata → trusted context → grounded answer → candidate answer → conversation → recommendation flow | `tests/e2e/test_local_assistant_flow.py` |
| Browser/widget | Framework-free rendering, text-node safety, recommendation behavior, and explicit preview/confirm/execute phases | `tests/web/widget.test.mjs`, manual local smoke |

Unit tests should own exhaustive pure validation. Contract tests should remain
adapter-neutral. Security tests should name the threat or invariant they exercise.
Integration tests may use SQLite and the synthetic mock adapter, but may not call a
live service. E2E tests use the public API through `httpx.ASGITransport`; they are
cross-endpoint tests, not a live HTTP deployment test.

## Prompt 20 traceability matrix

The IDs below are stable review references. Threat IDs refer to
[`THREAT_MODEL.md`](THREAT_MODEL.md).

| ID | Required behavior / threat | Automated evidence |
|---|---|---|
| QA-01 | Schema and input bounds | `tests/unit/test_domain_schemas.py`, `tests/unit/test_knowledge_loader.py`, `tests/unit/test_config.py` |
| QA-02 | Context validation | `tests/security/test_context_resolution.py`, `tests/integration/test_context_resolution_api.py` |
| QA-03 | Forged client role, email, permissions, or actions are rejected/ignored (T-01) | `test_client_supplied_identity_permission_and_action_fields_are_validation_errors`, `test_client_navigation_cannot_select_or_elevate_fixture_identity` |
| QA-04 | Missing or unverified identity fails closed (T-01) | `test_missing_and_unverified_identity_receive_no_candidate_data`, `test_missing_identity_returns_safe_refusal_and_identity_denial_audit` |
| QA-05 | Candidate visibility and guessed/private records do not leak (T-02) | `test_candidate_record_swap_is_denied_without_leaking_hidden_content`, `test_private_and_archived_candidates_remain_indistinguishable_from_missing` |
| QA-06 | Field redaction uses exact trusted grants; notes remain excluded (T-02) | `tests/security/test_identity_and_permissions.py`, `test_candidate_summary_is_redacted_grounded_and_not_persisted` |
| QA-07 | Approved feature/help retrieval and permission filtering (T-10) | `tests/unit/test_retrieval_service.py`, `tests/unit/test_knowledge_loader.py` |
| QA-08 | Source-aware grounded/verified answers | `test_assistant_returns_grounded_page_response_with_sources_and_request_id`, `tests/e2e/test_local_assistant_flow.py` |
| QA-09 | Unknown questions/features return unavailable without guessing | `test_unknown_feature_returns_no_source_without_guessing`, `test_unknown_question_is_honestly_unavailable_and_persisted` |
| QA-10 | Invented features, fake citations, unsupported claims/steps, and action-success prose are rejected (T-03, T-06) | `tests/security/test_provider_output_validation.py`, `tests/security/test_grounding_invariants.py` |
| QA-11 | Injection in questions, help bodies, candidate notes, and history remains untrusted data (T-03) | `tests/security/test_prompt_contracts.py`, `tests/security/fixtures/red_team_prompt_injection.json` |
| QA-12 | Recommendation acceptance/dismissal and repeated suppression | `test_feedback_lifecycle_records_all_types_and_dismissal_suppresses`, `test_acceptance_and_disabled_preference_prevent_repetition` |
| QA-13 | Recommendation opt-out | `test_acceptance_and_disabled_preference_prevent_repetition` (`disabled` preference) |
| QA-14 | Action execution requires a proposal, explicit confirmation, and a separate execute request (T-04) | `test_execution_before_explicit_confirmation_is_rejected_without_adapter_dispatch`, `test_proposal_preview_and_confirmation_are_persisted_without_execution`, widget phase test |
| QA-15 | Expired, reused, cancelled, wrong-user/workspace, parameter-, token-, target-, and version-tampered confirmations fail closed (T-04, T-05) | `tests/security/test_action_confirmation_state.py`, confirmation/execution conflict cases in `tests/integration/` |
| QA-16 | Permission and candidate visibility are revalidated between proposal and execution (T-01, T-04) | `test_permission_revoked_after_confirmation_is_rejected_without_adapter_write`, `test_candidate_visibility_revocation_is_terminal_once_without_adapter_dispatch` |
| QA-17 | Adapter timeout, malformed response/receipt, state conflict, validation failure, and unavailable outcomes remain typed and honest (T-06) | `tests/unit/test_apps_script_adapter.py`, `tests/integration/test_action_execution_api.py`, `test_adapter_timeout_or_unavailable_returns_503_with_no_data` |
| QA-18 | Success requires a matching owning-adapter receipt; ambiguous results never claim no change (T-06) | `test_success_requires_receipt_mutates_only_mock_state_and_writes_complete_audit`, timeout/unavailable/malformed-receipt tests, widget timeout test |
| QA-19 | Security-relevant audits are created and append-only (T-08) | `test_audit_records_are_append_only_in_repository_and_database`, context/action audit sequence assertions |
| QA-20 | Secrets, email, candidate notes, hidden fields, and tokens stay out of provider payloads, retained messages/feedback, events, audits, responses, and logs (T-02, T-07, T-08) | `tests/integration/test_sensitive_data_boundaries.py`, `tests/security/test_provider_payload_security.py`, `tests/unit/test_logging.py` |
| QA-21 | Exact CORS allowlist/preflight behavior and safe versioned errors (T-09) | `tests/security/test_cors_policy.py`, `tests/integration/test_request_ids_and_errors.py` |
| QA-22 | Conversations are isolated to verified user/workspace/app ownership | `test_conversation_isolated_to_verified_owner` |
| QA-23 | End-to-end local assistant flow is deterministic, source-aware, redacted, persisted, and offline | `tests/e2e/test_local_assistant_flow.py` |
| QA-24 | No pytest may open a live socket | autouse `block_live_network` in `tests/conftest.py`; `tests/security/test_no_live_network.py` verifies the guard |
| QA-25 | Fresh migration creates only approved OrkaFin tables; mock state resets independently (T-11) | `test_fresh_migration_creates_only_approved_orkafin_tables`, `test_mock_state_reset_rolls_back_values_and_clears_receipts`, clean release commands |
| QA-26 | Current repository files contain no high-confidence credential or private-key formats (T-07) | `scripts/scan_secrets.py`, `tests/security/test_repository_secret_scan.py` |

## Fixture and state reset strategy

- Every service/integration/E2E test receives a `tmp_path` SQLite database. Migration
  behavior is tested through Alembic; other service tests create the same current
  metadata directly for speed.
- `tests/conftest.py` tracks and disposes every test-created SQLAlchemy engine after
  dependent fixture teardown. This prevents open-connection leakage between tests.
- Action execution tests inject a unique `MockOrkaATSStateStore` path and call
  `reset()` before use. Assertions distinguish adapter-owned JSON state from the
  OrkaFin database.
- Catalog mutation tests clone the immutable loaded index and never rewrite checked-in
  knowledge.
- The release gate deletes only `var/orkafin.db`, resets mock adapter state, and then
  migrates from base to head. No test or reset command touches OrkaATS data.

## No-live-network rule

All pytest tests run under an autouse socket guard that raises on outbound
`socket.create_connection`, `socket.socket.connect`, or `connect_ex`. FastAPI tests
use in-process ASGI transport. External-provider and Apps Script adapter tests inject
recording/fake transports. A test that genuinely needs network access must not bypass
this fixture; it requires a reviewed test-strategy and architecture change.

The Node widget tests use only in-memory DOM/fetch fakes. The automated suite does
not contact a live AI provider, Apps Script deployment, Google Sheet, or real
candidate system.

## Coverage policy

`pytest-cov` is a bounded development dependency. Coverage measures branches and all
`orkafin` modules. `[tool.coverage.report]` enforces an 82.0% aggregate line/branch
floor. The floor is intentionally secondary to the threat matrix: a release cannot
trade away QA-03 through QA-26 to preserve an overall percentage.

The Prompt 20 measured baseline is 85.2% aggregate, comprising 89.2% statements and
66.5% branches. Representative critical-module aggregate results are context
resolution 88.1%, permission evaluation 89.0%, redaction 90.0%, action proposal
88.6%, action execution 80.1%, response generation 87.8%, grounding 90.5%, provider
validation 86.0%, and repositories 89.1%.

Explicit critical gaps in the coverage report are:

- defensive adapter-contract and Pydantic-invalid branches that valid typed callers
  cannot construct;
- action-execution database-race and multi-process behavior beyond the single-process
  SQLite/mock proof;
- the disabled Apps Script shell (69.3%) and external provider (66.7%), whose live
  transports, authentication, TLS, retention, and remote errors are intentionally not
  exercised;
- deterministic provider templates not selected by the current public assistant
  routing; and
- CLI entry-point lines for seed/knowledge validation/evaluation, which run as separate
  release commands and are not attributed to the pytest coverage process.

## Release gate

Run from the repository root with the development environment installed:

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

The dependency-free secret scan covers tracked and non-ignored untracked files,
sensitive filenames, private-key headers, and high-confidence provider credential
formats without printing matching values. It is not an entropy scan or full-history
scanner.

No lightweight vulnerability scanner was configured or installed when Prompt 20
started, so no dependency-vulnerability result is claimed. The exact recommended
operator commands are:

```bash
python -m pip install pip-audit
python -m pip_audit --local --strict
```

Add this as a mandatory release gate only after tool/version policy and dependency
locking are approved.

## Known residual risks and skipped tests

- Local fixture subject selection is a test harness, not production authentication.
- Structured claims, lexical checks, and finite injection fixtures do not prove
  semantic truth or complete prompt-injection resistance. Approved catalog content
  can still be wrong or malicious.
- The repository secret scan does not inspect Git history, use entropy heuristics, or
  replace a managed scanner and rotation process.
- No live provider/Apps Script test, real Google identity, Google Sheet access,
  production CORS/CSRF, TLS, rate limiting, multi-process action race, cloud load,
  backup/restore, or tamper-evident audit test is in scope.
- Property-based testing was not added: current ID/text bounds and redaction cases are
  strict typed invariants with targeted boundary/parameterized tests, and adding
  Hypothesis solely for test-count growth was not justified. Revisit when action or
  free-form field schemas expand.
- Browser layout, focus order, keyboard behavior, screen-reader output, and the visual
  offline/action demo still require the manual smoke checklist in `docs/LOCAL_SETUP.md`.
- A passing release gate states only what this local deterministic suite exercised; it
  does not establish that the system is secure or production-ready.
