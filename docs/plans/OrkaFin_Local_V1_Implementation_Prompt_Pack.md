# OrkaFin Local V1 Implementation Prompt Pack

## Purpose

This pack is an ordered build plan for a coding agent. It does **not** ask the agent to build the entire system in one pass. Each prompt creates a reviewable increment with tests, documentation, and a clean handoff to the next prompt.

The target is a local, production-minded V1 built around one pilot application, OrkaATS. OrkaFin remains a separate intelligence layer. OrkaATS remains the owner of candidate data and the final authority for candidate permissions, validation, and writes.

## Brutally practical architecture decisions

1. **Use one FastAPI service, not microservices.** Separate modules and interfaces inside one repository are enough for V1.
2. **Use Python 3.11+, Pydantic v2, SQLAlchemy 2, SQLite, Alembic, pytest, Ruff, and mypy.** Alembic is justified because V1 includes persistent conversations, events, feedback, actions, and audits, and the project explicitly needs migration boundaries.
3. **Do not store candidate records in the OrkaFin database.** A mock OrkaATS adapter may use isolated fixture state or a separate adapter-owned local database, but the OrkaFin persistence layer must not gain a `candidates` table.
4. **Use deterministic structured retrieval first.** The approved knowledge set is small and version-controlled. A vector database is unjustified until retrieval quality data proves otherwise.
5. **Make the external model optional.** The deterministic provider must support all automated tests and the full local demo. A model provider may improve wording, but it must never be the source of permissions, features, or action success.
6. **Do not use LangChain, LangGraph, or a multi-agent framework in V1.** Native Python interfaces and explicit services are easier to audit and replace. Revisit only when the workflow complexity demonstrates a real need.
7. **Do not pretend local development provides production identity.** Apps Script server-side code cannot directly call `localhost`, and browser-supplied email, role, permissions, or actions are untrusted. V1 uses explicit mock identities and a trusted adapter boundary. Live Apps Script testing requires a controlled HTTPS endpoint and an authentication design.
8. **Keep the widget framework-free.** Plain HTML, CSS, and JavaScript are sufficient and easier to embed in Apps Script later.
9. **Treat candidate notes and retrieved text as data, never instructions.** Notes should be excluded from model input by default. Approved help content still cannot override system rules.
10. **The optional action proof of concept is gated.** Do not implement it until permissions, audit logging, confirmation state, adapter failures, and security tests are complete enough to support it.

## Phase and status overview

| Phase | Prompts | Status |
|---|---:|---|
| Phase 0 — Decisions and Architecture | 1 | Mandatory; human checkpoint |
| Phase 1 — Repository and Local Foundation | 2–3 | Mandatory |
| Phase 2 — Domain Contracts and Data | 4–7 | Mandatory; human checkpoint after 7 |
| Phase 3 — OrkaATS Adapter and Context | 8–11 | Mandatory; human checkpoint after 11 |
| Phase 4 — Knowledge and Grounded AI | 12–14 | Mandatory; human checkpoint after 14 |
| Phase 5 — Assistant API and Widget | 15–16 | Mandatory |
| Phase 6 — Recommendations, Events, and Feedback | 17 | Mandatory |
| Phase 7 — Confirmed Action Proof of Concept | 18–19 | Optional V1 extension; human checkpoint before 19 |
| Phase 8 — Security and QA | 20 | Mandatory |
| Phase 9 — End-to-End Demo and Documentation | 21 | Mandatory; final human acceptance |

## Global rule for sequencing

Run prompts in order. Do not start the next prompt until the current prompt's tests pass and its acceptance criteria are met. At human checkpoints, stop and obtain review instead of making silent architecture changes.

---

# Phase 0 — Decisions and Architecture

## Prompt 1 — Freeze V1 Scope, Architecture, and Decision Records

**Status:** Mandatory — human review required before Prompt 2.

### Objective
Create the source-of-truth scope, architecture, threat boundaries, and ADRs before implementation.

### Why this comes first
Without a scope freeze, the coding agent will make accidental product decisions while scaffolding. That is how local prototypes become permanently coupled to Apps Script, Sheets, or a model provider.

### Prerequisites
- Empty repository or existing OrkaFin repository.
- The project brief and OrkaFin ecosystem constraints.

### Exact copy-paste prompt for the coding agent

```text
You are working on OrkaFin Local V1. Do not write application functionality yet.

Before changing anything:
1. Inspect the repository tree, README, existing documentation, git status, branches, and any current interfaces.
2. Preserve working files and decisions. Do not delete or rename existing functionality without documenting the reason.
3. If an earlier interface exists, refine it compatibly or record a migration plan. Never silently replace it.

Architecture constraints:
- Local-only V1; no AWS, GCP production deployment, Kubernetes, microservices, Kafka, Pub/Sub, Redis, vector database, multi-agent framework, continuous retraining, or autonomous actions.
- Python/FastAPI will be the local backend later, but this prompt is documentation-first.
- OrkaATS is the pilot and remains the owner of candidate data, permissions, business rules, and writes.
- OrkaFin must never read or write the OrkaATS Google Sheet directly.
- Browser-submitted email, role, permissions, and available actions are untrusted.
- Future Orka apps must connect through a versioned general adapter contract.
- Guidance is mandatory V1. A single confirmed action is optional and must be gated behind permissions, confirmation, adapter validation, audit logging, and failure handling.
- Structured deterministic retrieval is the initial knowledge approach. No vector database without measured evidence.
- External AI providers are optional. Tests and the local demo must work with a deterministic provider.

Create or substantially refine:
- README.md
- docs/V1_SCOPE_AND_NON_GOALS.md
- docs/ARCHITECTURE.md
- docs/SECURITY_MODEL.md
- docs/THREAT_MODEL.md
- docs/DECISIONS.md
- docs/FUTURE_MIGRATION_PLAN.md
- docs/adr/ADR-001-local-first-architecture.md
- docs/adr/ADR-002-application-data-ownership.md
- docs/adr/ADR-003-no-vector-database-for-initial-v1.md
- docs/adr/ADR-004-provider-independent-ai-interface.md

The architecture document must include:
- A component diagram in Mermaid.
- Trusted and untrusted boundaries.
- OrkaFin persistence versus OrkaATS-owned data.
- The request flow for guidance and for a confirmed action.
- A clear statement that local mock identity is not production authentication.
- Why Apps Script server-side code cannot be assumed to call localhost.

The threat model must cover:
- forged browser identity/role/permissions;
- candidate record leakage and field-level leakage;
- prompt injection in candidate notes and help documents;
- action parameter tampering;
- confirmation replay/expiry;
- fabricated success messages;
- secrets in frontend code or logs;
- audit log exposure;
- overly broad CORS.

The decisions file must list assumptions and unresolved questions, including authoritative OrkaATS stages, field visibility rules, deployment identity behavior, and the first optional action.

Do not create placeholder documents with one paragraph. Each file must contain concrete decisions, boundaries, verification steps, and change triggers.

Run any available documentation/link checks. If none exist, say so. Do not claim completion if checks fail.

At the end, report:
- files created/modified;
- decisions made;
- assumptions;
- unresolved risks;
- commands run and their results;
- the exact handoff information needed by Prompt 2.
```

### Files expected to be created or modified
- `README.md`
- `docs/V1_SCOPE_AND_NON_GOALS.md`
- `docs/ARCHITECTURE.md`
- `docs/SECURITY_MODEL.md`
- `docs/THREAT_MODEL.md`
- `docs/DECISIONS.md`
- `docs/FUTURE_MIGRATION_PLAN.md`
- `docs/adr/ADR-001-local-first-architecture.md`
- `docs/adr/ADR-002-application-data-ownership.md`
- `docs/adr/ADR-003-no-vector-database-for-initial-v1.md`
- `docs/adr/ADR-004-provider-independent-ai-interface.md`

### Required tests
- Documentation link/path validation if tooling already exists.
- Manual check that every required document has substantive content.

### Verification commands
```bash
git status --short
find docs -maxdepth 3 -type f | sort
rg -n "OrkaATS owns|direct.*Sheet|untrusted|vector database|mock identity|localhost" README.md docs
```

### Acceptance criteria
- Scope and non-goals are explicit.
- Candidate ownership boundary is unambiguous.
- Local identity limitations are stated honestly.
- Four ADRs exist and are internally consistent.
- Human reviewer approves the architecture before code scaffolding.

### Explicit non-goals
- No FastAPI application code.
- No database schema.
- No widget.
- No model-provider integration.

### Pass to the next prompt
- Approved package name and repository layout assumptions.
- Python version decision.
- Chosen persistence library.
- Any existing files that must remain compatible.
- Open questions that block scaffolding.

### Suggested Git commit message
`docs: freeze OrkaFin local V1 architecture and boundaries`

---

# Phase 1 — Repository and Local Foundation

## Prompt 2 — Scaffold the Typed Python Repository and Developer Tooling

**Status:** Mandatory.

### Objective
Create a minimal, maintainable repository layout and repeatable local development environment without implementing product logic.

### Why this comes now
The architecture is approved. The next step is to establish import boundaries, test structure, and quality gates before domain code spreads across arbitrary files.

### Prerequisites
- Prompt 1 approved.
- Python 3.11 or newer installed.

### Exact copy-paste prompt for the coding agent

```text
Implement the repository scaffold for OrkaFin Local V1.

First inspect all existing files, git status, and Prompt 1 documents. Preserve working functionality. Do not rename or delete established interfaces silently. If the repository already has a valid structure, adapt it rather than rebuilding it.

Constraints:
- One modular FastAPI service, not microservices.
- Python >=3.11.
- Pydantic v2, SQLAlchemy 2, Alembic, SQLite, pytest, Ruff, mypy, httpx.
- No LangChain, LangGraph, vector database, Redis, cloud deployment, or heavy frontend framework.
- OrkaFin must not own candidate records.
- Typed, maintainable code with tests in every increment.

Create a `src` layout with clear boundaries similar to:
- src/orkafin/api
- src/orkafin/core
- src/orkafin/domain
- src/orkafin/application
- src/orkafin/adapters
- src/orkafin/infrastructure
- src/orkafin/knowledge
- src/orkafin/providers
- src/orkafin/web
- tests/unit
- tests/integration
- tests/security
- tests/e2e
- scripts
- knowledge/orka_ats
- fixtures
- docs

Use a `pyproject.toml` as the dependency and tool configuration source. Choose compatible bounded versions based on the current environment; do not invent claims about “latest” versions. Add console or Makefile commands for install, format, lint, type-check, test, database migration, knowledge validation, and local run.

Create a minimal application factory and `/health` endpoint only. Do not add business endpoints yet. The application must start without external secrets and return a versioned health payload.

Add:
- `.gitignore`
- `.env.example` with names only and safe sample values
- `src/orkafin/__init__.py`
- `src/orkafin/main.py`
- application factory module
- a minimal settings module stub that Prompt 3 can complete
- test configuration and one health test
- `docs/LOCAL_SETUP.md`

Avoid global mutable state. Use dependency injection points, even if some dependencies are placeholders.

Required quality gates:
- Ruff check passes.
- Ruff format check passes.
- mypy passes for `src`.
- pytest passes.
- The app starts locally and `/health` responds.

Update architecture documentation only if scaffolding changes an approved decision. If it does, record the change in docs/DECISIONS.md.

At the end, provide a precise summary, files changed, commands and results, assumptions, unresolved risks, and the handoff to Prompt 3. Do not claim completion if any required command fails.
```

### Files expected to be created or modified
- `pyproject.toml`
- `.gitignore`
- `.env.example`
- `Makefile` or documented equivalent
- `src/orkafin/**`
- `tests/**`
- `docs/LOCAL_SETUP.md`
- `README.md`

### Required tests
- Application factory construction.
- `GET /health` returns 200 and expected schema.
- Import smoke test.

### Verification commands
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff format --check .
ruff check .
mypy src
pytest -q
uvicorn orkafin.main:app --reload
```

### Acceptance criteria
- Fresh clone setup is documented and repeatable.
- All quality gates pass.
- No product logic or candidate data ownership has leaked into the scaffold.
- Package boundaries match the approved architecture.

### Explicit non-goals
- No SQL models yet.
- No knowledge loader.
- No adapter implementation.
- No assistant UI beyond static package directories.

### Pass to the next prompt
- Final repository tree.
- Exact commands that pass.
- Python/dependency versions selected.
- Application factory and settings module paths.

### Suggested Git commit message
`build: scaffold typed local OrkaFin service`

---

## Prompt 3 — Configuration, Request IDs, Logging, and Error Envelope

**Status:** Mandatory.

### Objective
Implement safe local configuration, correlation IDs, structured logging, redaction, and a versioned API error model.

### Why this comes now
Every later feature depends on consistent settings, request tracing, and safe failures. Adding these after endpoints exist creates inconsistent logs and untestable error behavior.

### Prerequisites
- Prompt 2 passes all quality gates.

### Exact copy-paste prompt for the coding agent

```text
Add the configuration and observability foundation for OrkaFin Local V1.

Before editing, inspect the current repository, Prompt 1 decisions, Prompt 2 scaffold, and git status. Preserve working behavior. Do not replace public interfaces silently.

Constraints:
- Local-only service.
- Secrets must never be returned to the frontend or logged.
- Logs must exclude tokens, passwords, full candidate notes, raw model prompts, and unnecessary private content.
- Browser-supplied identity fields remain untrusted.
- Use typed code, tests, and documentation updates.

Implement:
1. A Pydantic Settings configuration with environment prefixes and safe defaults for local development.
2. Environment variables for app environment, database URL, log level, allowed local origins, AI provider selection, optional provider key, confirmation TTL, and fixture mode.
3. Validation that rejects unsafe production-like combinations, such as enabling an external provider without a server-side key or wildcard CORS with credentials.
4. Request/correlation ID middleware. Accept a syntactically valid incoming request ID only if policy allows; otherwise generate one. Return it in a response header and include it in errors and logs.
5. Structured JSON-compatible logging with a redaction filter for keys such as authorization, cookie, token, secret, password, api_key, notes, and raw_content.
6. A versioned `ApiError` response schema with error code, safe message, request ID, optional safe details, and no traceback leakage.
7. Central exception handlers for validation errors, domain errors, adapter errors, and unexpected exceptions.
8. A development-only debug option that still does not expose secrets in API responses.

Document every environment variable in `.env.example` and `docs/LOCAL_SETUP.md`. Add `docs/ERROR_HANDLING.md` only if the material would otherwise make another document unwieldy.

Tests must prove:
- request IDs are generated and returned;
- malformed request IDs are replaced;
- secrets are redacted from captured logs;
- validation errors use the API error envelope;
- unexpected errors return a safe message and request ID;
- wildcard credentialed CORS is rejected;
- missing optional model keys do not block deterministic mode.

Run Ruff, mypy, and the full test suite. Do not claim completion if any command fails. End with files changed, commands/results, assumptions, risks, and the handoff to Prompt 4.
```

### Files expected to be created or modified
- `src/orkafin/core/config.py`
- `src/orkafin/core/logging.py`
- `src/orkafin/core/request_id.py`
- `src/orkafin/core/errors.py`
- application factory files
- `.env.example`
- `docs/LOCAL_SETUP.md`
- tests for config, logging, middleware, and errors

### Required tests
- Configuration validation.
- Correlation ID behavior.
- Redaction behavior.
- Error schema consistency.
- CORS safety.

### Verification commands
```bash
ruff format --check .
ruff check .
mypy src
pytest -q
```

### Acceptance criteria
- Every response can be correlated to a request ID.
- Error responses never expose tracebacks or secrets.
- Deterministic local mode runs with no external key.
- Configuration is explicit and documented.

### Explicit non-goals
- No database logging yet.
- No business audit records yet.
- No external model call.

### Pass to the next prompt
- Settings class fields and defaults.
- Error code conventions.
- Request ID format and header name.
- Logging redaction rules.

### Suggested Git commit message
`feat: add safe configuration logging and API error envelope`

---

# Phase 2 — Domain Contracts and Data

## Prompt 4 — Define Versioned Domain Schemas and Ownership Boundaries

**Status:** Mandatory.

### Objective
Create the canonical domain contracts that every later service, adapter, endpoint, and test will use.

### Why this comes now
The most expensive failure would be coding services against vague dictionaries. Typed contracts force decisions about trust, ownership, sensitivity, and versioning before persistence and adapters harden accidental assumptions.

### Prerequisites
- Prompts 1–3 complete.

### Exact copy-paste prompt for the coding agent

```text
Define OrkaFin's versioned domain models. Do not implement business workflows yet.

Inspect all existing code and documents before changing anything. Preserve established interfaces. If you must change an earlier public type, provide a compatibility path and update docs/DECISIONS.md.

Architecture constraints:
- OrkaATS owns candidate data. OrkaFin may receive a controlled `CandidateSummary`, but it must not define a candidate persistence model.
- Client context is untrusted. Adapter-verified context is trusted only for the adapter response lifetime.
- Every model must identify ownership and sensitive-field handling.
- Use Pydantic v2 models, enums, discriminated unions where useful, strict validation, UTC timestamps, and explicit schema versions.
- Avoid generic `dict[str, Any]` except for deliberately bounded metadata with validation.

Create schemas for at least:
- AppMetadata
- ClientContextHint
- ResolvedPageContext
- UserIdentity and IdentityVerificationStatus
- Role and Permission
- WorkspaceRef
- SelectedEntityRef
- CandidateSummary with field visibility/redaction metadata
- FeatureCatalogItem
- PageCatalogItem
- HelpArticle
- UserEvent
- Recommendation and RecommendationFeedback
- Conversation and Message
- RetrievedSource
- GroundingStatus and AssistantResponse
- ActionDefinition
- ActionProposal
- ActionConfirmation
- ActionExecutionResult
- AuditRecord
- ApiError or reuse the existing error schema
- RequestId/CorrelationId validated value object

Required contract rules:
- Separate client-claimed fields from adapter-verified fields.
- Candidate notes are absent from the default candidate summary. If an optional notes excerpt exists, label it untrusted and sensitive.
- Permissions use namespaced strings such as `candidate.view` and `candidate.update_start_date`.
- Sources include source ID, source type, app ID, version/revision, title, and a safe reference.
- Assistant responses distinguish verified fact, grounded guidance, recommendation, refusal, unavailable information, and action proposal.
- Action results cannot represent success without an adapter execution receipt.
- Timestamps are timezone-aware UTC.
- IDs have length and character constraints.
- Schema examples are included without real personal data.

Create `docs/DOMAIN_MODEL.md` with an ownership table and examples. Update the adapter contract document stub if needed, but do not implement adapters.

Add comprehensive schema tests for valid examples and rejection of malformed versions, IDs, timestamps, permissions, unsupported enum values, oversized text, and illegal success results.

Run all quality gates. Finish with a summary, files changed, tests/results, assumptions, unresolved questions, and the exact handoff to Prompt 5.
```

### Files expected to be created or modified
- `src/orkafin/domain/**`
- `docs/DOMAIN_MODEL.md`
- `docs/DECISIONS.md`
- unit tests for all schemas

### Required tests
- Valid/invalid schema tests.
- UTC timestamp enforcement.
- Strict enum/version validation.
- Client versus verified context separation.
- Candidate notes excluded by default.
- Action success requires adapter receipt.

### Verification commands
```bash
ruff format --check .
ruff check .
mypy src
pytest -q tests/unit
pytest -q
```

### Acceptance criteria
- No core workflow relies on untyped dictionaries.
- Ownership boundaries are documented.
- Client and trusted context cannot be confused by type.
- Candidate persistence is not introduced.

### Explicit non-goals
- No SQL tables.
- No permission evaluator.
- No adapter calls.
- No retrieval logic.

### Pass to the next prompt
- Public schema module paths.
- Schema version values.
- ID conventions.
- Sensitive-field classifications.
- Any unresolved domain choices requiring human input.

### Suggested Git commit message
`feat: define versioned OrkaFin domain contracts`

---

## Prompt 5 — Add OrkaFin Persistence and Alembic Migrations

**Status:** Mandatory.

### Objective
Persist only OrkaFin-owned state: conversations, messages, events, recommendations, feedback, action state, and audits.

### Why this comes now
Persistence should follow domain contracts, not define them. This step also enforces the crucial boundary that candidate records are not stored as OrkaFin business data.

### Prerequisites
- Prompt 4 schemas approved.

### Exact copy-paste prompt for the coding agent

```text
Implement the SQLite persistence layer and Alembic migrations for OrkaFin-owned data.

Before editing, inspect the repository, domain contracts, architecture docs, and git status. Preserve working behavior and public interfaces. Do not silently alter Prompt 4 schemas.

Hard boundary:
- Do not create a `candidates` table or any general OrkaATS record mirror in the OrkaFin database.
- Candidate IDs may appear only as bounded references in messages, events, recommendations, action proposals, or audits where needed.
- OrkaATS fixture state, if required later, must live behind the mock adapter and be isolated from OrkaFin persistence.

Use SQLAlchemy 2 typed declarative models, a repository/unit-of-work pattern only where it reduces coupling, and Alembic migrations. Keep the design simple; do not invent a generic enterprise data layer.

Implement tables for:
- conversations
- messages
- user_events
- recommendation_impressions or recommendations_shown
- recommendation_feedback
- action_proposals
- action_confirmations
- action_executions
- audit_records

Include appropriate:
- UUID/string identifiers;
- schema version columns where records need versioning;
- created/updated UTC timestamps;
- status enums and check constraints;
- foreign keys and indexes;
- immutable or append-only semantics for audit records;
- unique idempotency keys where later action execution needs them;
- bounded JSON columns only for validated, non-sensitive parameters.

Do not store raw model prompts, API keys, passwords, tokens, full candidate notes, or arbitrary browser context. Add a persistence serialization layer that accepts validated domain objects rather than raw request bodies.

Add:
- database session dependency;
- local database initialization command;
- Alembic configuration;
- initial migration;
- test database fixtures using temporary SQLite files;
- repository tests;
- migration upgrade/downgrade test where practical.

Document the data model and retention assumptions in `docs/EVENT_AND_AUDIT_MODEL.md`. Include a table showing which fields may contain candidate references and why.

Run Alembic from an empty database, full tests, Ruff, and mypy. Do not claim completion if migration or tests fail. Report files, commands/results, assumptions, risks, and handoff to Prompt 6.
```

### Files expected to be created or modified
- `src/orkafin/infrastructure/database/**`
- `alembic.ini`
- `migrations/**`
- database repositories
- `docs/EVENT_AND_AUDIT_MODEL.md`
- database tests

### Required tests
- Fresh migration upgrade.
- Repository CRUD for OrkaFin-owned records.
- Constraint and foreign-key tests.
- Audit append-only behavior.
- No candidate table assertion.
- Sensitive-field serialization exclusion.

### Verification commands
```bash
rm -f var/orkafin.db
alembic upgrade head
alembic current
ruff format --check .
ruff check .
mypy src
pytest -q
```

### Acceptance criteria
- Empty clone can create the database through migrations.
- OrkaFin-owned state persists.
- Candidate records are not mirrored into OrkaFin.
- Audit records are immutable through normal repositories.

### Explicit non-goals
- No knowledge in the database.
- No candidate fixture storage in the OrkaFin database.
- No action execution logic.

### Pass to the next prompt
- Database URL format.
- Migration revision ID.
- Repository interfaces.
- Retention assumptions.
- Idempotency field design.

### Suggested Git commit message
`feat: add OrkaFin persistence and initial migrations`

---

## Prompt 6 — Create Version-Controlled Knowledge Catalogs and Loader

**Status:** Mandatory.

### Objective
Define and load the authoritative starter knowledge for OrkaATS: app metadata, pages, features, help, recommendations, permissions, and actions.

### Why this comes now
Grounded responses require approved sources. The catalog must exist before retrieval or AI generation, otherwise the model will become the de facto source of truth.

### Prerequisites
- Prompts 4–5 complete.
- Initial OrkaATS concepts available, even if marked as starter assumptions.

### Exact copy-paste prompt for the coding agent

```text
Create the version-controlled OrkaATS knowledge model and validation pipeline.

Inspect existing files, domain schemas, and docs before editing. Preserve prior interfaces. Do not replace schema contracts silently.

Constraints:
- Knowledge remains in JSON/YAML/Markdown under version control for V1.
- No vector database or embeddings.
- Every knowledge item must be approved-source content with an owner, status, version/revision, and last-reviewed date.
- Starter fields and stages are assumptions, not authoritative production truth. Mark them clearly and document how to replace them.
- The model must not invent features or steps that are absent from the catalog.

Create a structure such as:
- knowledge/orka_ats/app.yaml
- knowledge/orka_ats/pages.yaml
- knowledge/orka_ats/features.yaml
- knowledge/orka_ats/permissions.yaml
- knowledge/orka_ats/recommendations.yaml
- knowledge/orka_ats/actions.yaml
- knowledge/orka_ats/help/*.md
- knowledge/orka_ats/manifest.yaml

Starter pages:
- candidate_dashboard
- candidate_list
- candidate_profile
- candidate_creation_form
- recruitment_pipeline
- recruiter_filters

Starter concepts:
- immutable candidate ID
- candidate name
- email
- recruiter
- recruitment stage
- start date
- resume link
- notes only where permitted
- created/updated timestamps

Starter stages, clearly labeled provisional:
- Contacted
- Interview Scheduled
- Pre-Onboarding
- Onboarding
- Active
- Paused
- Meeting No Show
- Archived

For each feature/page/help article include aliases, purpose, supported roles/permissions, page links, step sequence where verified, related items, status, version, owner, and source reference. Do not fabricate exact button names if not verified; use an explicit `verification_status` and safe uncertainty wording.

Implement a typed loader and validator that:
- validates files against Prompt 4 schemas;
- rejects duplicate IDs and dangling references;
- rejects unknown permissions/actions;
- verifies source files exist;
- enforces active/deprecated status rules;
- produces a deterministic in-memory index;
- exposes a CLI command for validation and summary counts.

Create `docs/KNOWLEDGE_MODEL.md` and document the authoritative-update workflow, review ownership, and how a bad knowledge change is rolled back.

Tests must cover valid loading, duplicates, dangling references, invalid versions, deprecated items, missing help files, malformed Markdown metadata, and deterministic ordering.

Run knowledge validation plus all quality gates. Do not claim completion with invalid starter data. End with summary, assumptions, unresolved OrkaATS facts, risks, and handoff to Prompt 7.
```

### Files expected to be created or modified
- `knowledge/orka_ats/**`
- `src/orkafin/knowledge/**`
- validation CLI/script
- `docs/KNOWLEDGE_MODEL.md`
- tests for catalogs and loader

### Required tests
- Catalog schema validation.
- Duplicate and dangling-reference rejection.
- Provisional/verified status behavior.
- Deterministic load order.
- Unknown permission/action rejection.

### Verification commands
```bash
python -m orkafin.knowledge.validate knowledge/orka_ats
ruff format --check .
ruff check .
mypy src
pytest -q
```

### Acceptance criteria
- Starter knowledge loads deterministically.
- Every answerable feature and page has a source reference.
- Unverified instructions are clearly marked.
- There is a documented path to replace starter definitions with authoritative OrkaATS data.

### Explicit non-goals
- No semantic embeddings.
- No web crawling.
- No model-generated knowledge.
- No live Google Docs ingestion.

### Pass to the next prompt
- Knowledge IDs and manifest version.
- Provisional facts requiring team confirmation.
- Loader/index API.
- Validation command.

### Suggested Git commit message
`feat: add validated OrkaATS knowledge catalogs`

---

## Prompt 7 — Implement Local Identity Fixtures, Permissions, and Field Redaction

**Status:** Mandatory — human review required before Prompt 8.

### Objective
Create the local authorization model, fixture users, permission evaluator, and field-level candidate summary redaction.

### Why this comes now
Adapters and context resolution must call a permission system. Deferring it would force security checks into endpoints or model prompts, which is unacceptable.

### Prerequisites
- Domain schemas and knowledge permissions exist.
- Human can review provisional roles and field visibility.

### Exact copy-paste prompt for the coding agent

```text
Implement the local V1 identity, authorization, and redaction layer.

Inspect the repository, domain contracts, security docs, knowledge permissions, and git status first. Preserve established interfaces. Do not silently change permission names or domain models.

Non-negotiable rules:
- Browser-submitted email, role, permission list, and available actions are untrusted claims.
- Local fixture authentication is a test harness, not production authentication. Label it explicitly in code and docs.
- OrkaFin may never broaden access beyond what the trusted application adapter verifies.
- Deny by default.
- Candidate notes are excluded unless a specific field permission exists; even then, treat them as sensitive and untrusted data.

Implement:
1. Local fixture users with at least admin, recruiter, limited viewer, and unauthenticated/unverified identities.
2. A typed `IdentityResolver` interface and a `LocalFixtureIdentityResolver` implementation.
3. A permission evaluator supporting app, page, record, field, and action checks without embedding logic in API routes.
4. A `CandidateSummaryRedactor` that returns only permitted fields and includes redaction metadata without revealing hidden values.
5. Clear denial reasons/codes suitable for safe user messages and audit records.
6. Tests where a client claims admin or adds permissions but the resolver/adapter returns a lower-privilege identity.
7. Fixture data documentation with no real personal information.

Suggested policy examples to encode as provisional fixtures:
- recruiter: view assigned/allowed candidates; view standard fields; update start date only when action permission is present;
- limited viewer: view candidate name, stage, and recruiter only;
- admin: broader visibility but still no secrets or raw private notes by default;
- unverified identity: no candidate data.

Do not assume role alone grants access. The evaluator must accept trusted permission and record-visibility inputs from the adapter. Keep role mapping separate from the final authorization decision.

Create or refine:
- docs/PERMISSION_MODEL.md
- docs/SECURITY_MODEL.md
- fixture user files
- permission/redaction services

Tests must cover missing identity, forged client role, candidate visibility restrictions, field-level redaction, missing action permission, unknown permission, deny-by-default, and safe denial messages.

Run all quality gates. Stop for human review of roles, permissions, and field visibility. Do not proceed on your own if these remain ambiguous. End with summary, files, results, assumptions, unresolved policy choices, and handoff to Prompt 8.
```

### Files expected to be created or modified
- `src/orkafin/application/auth/**`
- `src/orkafin/application/permissions/**`
- `fixtures/users.*`
- `docs/PERMISSION_MODEL.md`
- security tests

### Required tests
- Forged role/permission rejection.
- Missing identity denial.
- Record visibility denial.
- Field redaction by role/permission.
- Deny-by-default.
- Safe error text.

### Verification commands
```bash
ruff format --check .
ruff check .
mypy src
pytest -q tests/security tests/unit
pytest -q
```

### Acceptance criteria
- Client claims cannot elevate access.
- Candidate summaries are field-filtered by trusted policy inputs.
- Unverified identities receive no candidate data.
- Human reviewer approves provisional access matrix.

### Explicit non-goals
- No Google OAuth.
- No production Workspace identity integration.
- No endpoint authorization yet.

### Pass to the next prompt
- Approved fixture users.
- Permission naming and access matrix.
- IdentityResolver and permission evaluator interfaces.
- Redaction behavior and denial codes.

### Suggested Git commit message
`feat: add local identity permissions and candidate redaction`

---

# Phase 3 — OrkaATS Adapter and Context

## Prompt 8 — Define the General Orka Application Adapter Contract

**Status:** Mandatory.

### Objective
Create the versioned, application-neutral adapter interface that OrkaATS and future Orka apps will implement.

### Why this comes now
The permission model exists. The adapter must now define which trusted facts an owning application can provide and how OrkaFin requests actions without coupling to Sheets or Apps Script internals.

### Prerequisites
- Prompts 4 and 7 interfaces approved.

### Exact copy-paste prompt for the coding agent

```text
Define the general Orka application adapter contract and dependency-injection boundary.

Inspect all existing code and documentation first. Preserve prior contracts. Do not rename domain or permission interfaces without a documented migration.

Architecture constraints:
- OrkaFin is application-neutral.
- Each Orka app owns its records, business rules, permissions, and writes.
- No adapter may expose unrestricted database/Sheet access.
- Every adapter and request/response schema is versioned.
- All state-changing calls require an action definition, trusted identity, confirmation state, idempotency key, and request ID.
- Adapter failures must be explicit and must never be converted into success.

Define typed asynchronous interfaces for capabilities equivalent to:
- get_app_metadata
- resolve_current_user
- resolve_context
- get_user_permissions
- get_page_metadata
- get_selected_entity_summary
- get_available_features
- get_available_actions
- get_recent_user_events
- search_allowed_records
- execute_approved_action
- log_feedback

Improve names and split methods where needed, but keep responsibilities clear. Do not create a giant generic `call(action, payload)` interface as the only contract.

Add:
- adapter capability/version metadata;
- typed adapter errors: unavailable, unauthorized, forbidden, not found, validation failed, conflict, timeout, and internal failure;
- execution receipt schema that includes owning app, action ID, target reference, timestamp, outcome, and adapter transaction/reference ID;
- adapter registry/factory using dependency injection;
- contract tests that every adapter implementation must pass;
- a fake minimal adapter used only to test the contract.

Create `docs/ORKA_APP_ADAPTER_CONTRACT.md` and `docs/ORKA_ATS_ADAPTER_CONTRACT.md`. The general document should explain how another Orka app onboards. The OrkaATS document should map candidate context and allowed action semantics without describing direct Sheet access.

Do not implement the real or mock OrkaATS adapter in this prompt beyond a tiny contract test fake.

Run all quality gates. Finish with files, commands/results, interface decisions, assumptions, unresolved risks, and handoff to Prompt 9. Do not claim completion if contract tests fail.
```

### Files expected to be created or modified
- `src/orkafin/adapters/base.py` or equivalent
- adapter errors and registry
- contract test utilities
- `docs/ORKA_APP_ADAPTER_CONTRACT.md`
- `docs/ORKA_ATS_ADAPTER_CONTRACT.md`

### Required tests
- Contract conformance fake.
- Error mapping.
- Adapter registry resolution.
- Execution receipt validation.
- Unsupported capability behavior.

### Verification commands
```bash
ruff format --check .
ruff check .
mypy src
pytest -q tests/unit tests/integration
pytest -q
```

### Acceptance criteria
- No OrkaATS-specific fields leak into the general interface where a generic entity reference is sufficient.
- Sensitive reads and writes require trusted adapter involvement.
- Future apps can implement the contract without copying OrkaATS code.

### Explicit non-goals
- No mock candidate fixtures.
- No HTTP Apps Script client.
- No context endpoint.

### Pass to the next prompt
- Adapter protocol names/signatures.
- Error types.
- Registry mechanism.
- Contract test suite entry point.

### Suggested Git commit message
`feat: define versioned Orka application adapter contract`

---

## Prompt 9 — Implement the Mock OrkaATS Adapter and Realistic Fixtures

**Status:** Mandatory.

### Objective
Provide a deterministic, permission-aware OrkaATS implementation for local development and tests.

### Why this comes now
The full local V1 must work without Apps Script or a tunnel. A mock adapter is not a toy; it is the reference implementation of ownership and authorization boundaries.

### Prerequisites
- General adapter contract complete.
- Fixture access matrix approved.

### Exact copy-paste prompt for the coding agent

```text
Implement a realistic mock OrkaATS adapter that conforms to the general adapter contract.

Inspect all existing code, fixtures, contracts, and docs before editing. Preserve public interfaces. Do not change the adapter protocol silently.

Hard rules:
- The mock adapter represents OrkaATS ownership. OrkaFin services must access candidate data only through this adapter.
- Do not add candidate tables to the OrkaFin database.
- Use synthetic candidate fixtures only. No real people or production exports.
- The adapter must verify identity, record visibility, field access, available actions, and business rules.
- Client-provided roles/permissions are ignored.
- Candidate notes are excluded from normal summaries and model input.

Implement:
- app metadata and page metadata for the starter pages;
- fixture users/workspaces/candidates with at least allowed, restricted, archived, and missing candidate cases;
- candidate summaries with field-level redaction;
- available feature/action calculation;
- recent meaningful events fixtures;
- allowed-record search with strict result limits and field filtering;
- deterministic adapter failures and latency/timeout simulation hooks for tests;
- optional isolated adapter-owned state for later action tests. If persistence is needed, use a separate mock OrkaATS store that is not imported by OrkaFin persistence repositories.

The adapter must pass the contract test suite from Prompt 8.

Create fixtures for scenarios:
- recruiter can view CAND-1042 and standard fields;
- recruiter cannot view a private candidate;
- limited viewer sees a reduced summary;
- admin has broader but still bounded visibility;
- unverified user gets no candidate data;
- a candidate contains malicious note text that must never become an instruction;
- adapter unavailable and validation failure cases.

Add `docs/MOCK_ORKA_ATS.md` describing the fixture model, reset command, and limitations.

Tests must prove no service can retrieve a full candidate object, redaction is enforced inside the adapter, private records remain hidden, and simulated errors return typed adapter failures.

Run all quality gates. End with summary, files, results, assumptions, risks, and handoff to Prompt 10. Do not claim completion if adapter contract tests fail.
```

### Files expected to be created or modified
- `src/orkafin/adapters/orka_ats/mock.py`
- `fixtures/orka_ats/**`
- mock reset/seed utilities
- `docs/MOCK_ORKA_ATS.md`
- adapter contract/integration/security tests

### Required tests
- Adapter contract suite.
- Visibility and redaction.
- Missing/unverified identity.
- Search limits.
- Malicious note isolation.
- Typed failure simulation.

### Verification commands
```bash
python -m orkafin.adapters.orka_ats.seed --reset
ruff format --check .
ruff check .
mypy src
pytest -q tests/integration tests/security
pytest -q
```

### Acceptance criteria
- Full local candidate context can be exercised without Apps Script.
- OrkaFin never accesses fixture files directly outside the adapter.
- Restricted candidates and fields do not leak.
- Mock adapter conforms to the general contract.

### Explicit non-goals
- No live Apps Script requests.
- No assistant responses yet.
- No state-changing action execution unless required only as a disabled stub.

### Pass to the next prompt
- Mock adapter registration key.
- Fixture user/candidate IDs.
- Reset command.
- Supported pages/features/actions.
- Failure simulation options.

### Suggested Git commit message
`feat: add permission-aware mock OrkaATS adapter`

---

## Prompt 10 — Specify the Real Apps Script Adapter and Local Integration Options

**Status:** Mandatory documentation and boundary implementation.

### Objective
Define the future real OrkaATS integration without pretending localhost is directly reachable from Apps Script server-side code.

### Why this comes now
The mock contract is concrete enough to define the live boundary. This prevents the local demo from becoming a dead-end one-off.

### Prerequisites
- Mock adapter and general contract exist.
- Current OrkaATS Apps Script architecture is understood at a high level.

### Exact copy-paste prompt for the coding agent

```text
Define the real OrkaATS Apps Script adapter contract and implement only the safe client boundary that can be tested locally with mocked HTTP responses.

Inspect existing adapter contracts, docs, and code first. Preserve interfaces. Do not replace the mock adapter or couple core services to HTTP.

Be technically honest:
- Apps Script server-side code cannot be assumed to call a developer's localhost.
- A browser page may call localhost during controlled development, but identity from that browser request is untrusted and CORS/mixed-content restrictions apply.
- Controlled live testing may use a temporary HTTPS tunnel, but that is not production architecture.
- A later hosted OrkaFin API requires real authentication, request signing/token exchange, replay protection, and deployment review.

Create/refine `docs/ORKA_ATS_ADAPTER_CONTRACT.md` with:
- versioned request and response envelopes;
- operation names mapped to the general adapter contract;
- trusted identity assertions and what OrkaFin must verify;
- record/field/action permission behavior;
- error codes and retry rules;
- request ID and idempotency propagation;
- action execution receipt;
- timeout limits;
- no direct Sheet references in the public contract;
- compatibility/version negotiation;
- sample Apps Script `doPost` routing pseudocode, not production code;
- four local integration modes: mock adapter, browser-local demo, controlled HTTPS tunnel, later hosted API;
- security requirements before any live candidate data is used.

Implement an `AppsScriptOrkaATSAdapter` HTTP client shell behind the existing interface using an injected transport. It must be disabled by default and must not contain hard-coded URLs or secrets. Support typed serialization, timeout, safe error mapping, and request ID propagation. Do not implement production auth. Refuse to start in live mode unless required configuration is present.

Tests must use mocked HTTP transport and cover success parsing, schema-version mismatch, timeout, malformed response, permission denial, action receipt validation, and secret-free logs.

Update future migration docs and decisions. Run all quality gates. End with files, commands/results, assumptions, risks, and handoff to Prompt 11. Do not claim that live Apps Script integration is complete.
```

### Files expected to be created or modified
- `docs/ORKA_ATS_ADAPTER_CONTRACT.md`
- `docs/FUTURE_MIGRATION_PLAN.md`
- `src/orkafin/adapters/orka_ats/apps_script.py`
- transport abstractions/config
- mocked HTTP tests

### Required tests
- Request/response serialization.
- Version mismatch.
- Timeout and malformed response mapping.
- Permission denial mapping.
- No secrets in logs.
- Disabled-by-default behavior.

### Verification commands
```bash
ruff format --check .
ruff check .
mypy src
pytest -q tests/unit tests/integration
pytest -q
```

### Acceptance criteria
- Real integration boundary is explicit and versioned.
- No claim that localhost or live auth works magically.
- Core services remain unaware of HTTP versus mock adapters.
- Live mode cannot start with incomplete config.

### Explicit non-goals
- No deployment.
- No production OAuth or request signing implementation.
- No live candidate traffic.
- No Apps Script Sheet logic.

### Pass to the next prompt
- HTTP envelope version.
- Adapter config fields.
- Known production-auth gaps.
- Mock transport fixtures.

### Suggested Git commit message
`docs: specify Apps Script adapter and local integration boundary`

---

## Prompt 11 — Resolve Trusted Context from Untrusted UI Hints

**Status:** Mandatory — human review required before Prompt 12.

### Objective
Implement the context resolution flow that separates UI hints from adapter-verified identity, permissions, page, and candidate summary.

### Why this comes now
Retrieval and responses need trusted current-page context. The system must not pass browser claims straight into prompts or authorization checks.

### Prerequisites
- Identity/permission services.
- General and mock adapter.
- Domain context models.

### Exact copy-paste prompt for the coding agent

```text
Implement OrkaFin's trusted context resolution service and API endpoint.

Inspect existing schemas, adapters, permission services, errors, docs, and git status before changing anything. Preserve public interfaces. Do not merge client and trusted context models.

Required flow:
1. Receive a `ClientContextHint` containing app ID, page hint, selected entity reference, and optional client request ID.
2. Resolve the configured adapter by app ID.
3. Resolve identity through the trusted local identity resolver/adapter session, not from client email or role fields.
4. Ask the adapter to validate page/context and selected entity visibility.
5. Retrieve trusted permissions and available actions.
6. Retrieve a redacted selected candidate summary only when permitted.
7. Produce a `ResolvedPageContext` that labels source/trust for each component.
8. Write audit records for sensitive candidate reads and denied permission checks, without logging hidden fields or raw candidate notes.

Add a versioned endpoint, preferably `POST /api/v1/contexts:resolve` or another consistent REST shape. Document the naming rationale. The response must never echo untrusted role or permission claims as trusted values.

Safe behavior:
- unverified identity: return the established safe refusal and no candidate data;
- missing selected candidate: return context with no entity, not a fabricated candidate;
- candidate not visible: safe 403/error envelope and audit denial;
- unknown app/page: safe unavailable response;
- adapter unavailable: safe failure stating no data was returned.

Tests must include:
- client claims admin but fixture identity is limited;
- client submits extra permissions/actions;
- client swaps candidate ID to a private record;
- missing identity;
- missing candidate selection;
- unknown app/page;
- adapter timeout;
- successful context with correct redaction;
- sensitive read and denial audit creation;
- no hidden values in logs or API response.

Update architecture, permission, and API docs. Run migrations if audit persistence changed. Run full quality gates. Stop for human review of the resolved context example and audit behavior. End with files, commands/results, assumptions, risks, and handoff to Prompt 12.
```

### Files expected to be created or modified
- `src/orkafin/application/context/**`
- context API router
- audit integration
- `docs/API.md` or equivalent
- context/security/integration tests

### Required tests
- Forged context claims.
- Record-swap attack.
- Missing identity/context.
- Redacted success.
- Adapter failure.
- Audit creation and log redaction.

### Verification commands
```bash
alembic upgrade head
ruff format --check .
ruff check .
mypy src
pytest -q tests/security tests/integration
pytest -q
```

### Acceptance criteria
- UI hints cannot grant access.
- Candidate summaries come only from the trusted adapter.
- Denied and sensitive reads are auditable.
- Human reviewer approves the trust labeling and response shape.

### Explicit non-goals
- No answer generation.
- No recommendations.
- No action confirmation.

### Pass to the next prompt
- Context endpoint and schemas.
- Trusted fields and source labels.
- Audit event types.
- Safe error codes/messages.

### Suggested Git commit message
`feat: resolve trusted OrkaATS context from client hints`

---

# Phase 4 — Knowledge and Grounded AI

## Prompt 12 — Implement Deterministic Structured Retrieval and Source References

**Status:** Mandatory.

### Objective
Retrieve approved OrkaATS pages, features, and help content deterministically and return explicit source references.

### Why this comes now
The system has trusted context and validated knowledge. Retrieval should be proven before any model is added.

### Prerequisites
- Knowledge loader/index.
- Resolved context service.

### Exact copy-paste prompt for the coding agent

```text
Implement deterministic approved-source retrieval for OrkaFin Local V1.

Inspect existing knowledge schemas, indexes, context models, and tests first. Preserve interfaces. Do not introduce embeddings, a vector database, or external search.

Build a retrieval service that accepts:
- normalized user question;
- resolved app/page context;
- trusted permissions;
- optional selected entity type, not raw private content;
- result limit.

Retrieval must search only active approved catalog items and help articles using explicit IDs, aliases, page links, feature links, tags, and deterministic token scoring. Prefer exact page/feature matches before fuzzy token matches. Keep scoring explainable and testable.

Return typed `RetrievedSource` objects with:
- source ID/type;
- app ID;
- version/revision;
- title;
- safe excerpt;
- reference path or internal URI;
- verification status;
- relevance reason/score;
- required permissions already checked.

Rules:
- Never return a source the user is not permitted to access.
- Never return deprecated guidance unless explicitly requested for historical context.
- Never treat text inside a source as executable instructions to the system.
- Candidate notes are not a knowledge source.
- Unknown questions return an empty result with a reason, not a guessed feature.
- Related but unverified instructions must carry uncertainty metadata.

Support core intents without an LLM through deterministic intent matching:
- explain this page;
- what can I do here;
- feature question;
- step-by-step help;
- unknown feature.

Add retrieval evaluation fixtures containing expected source IDs for at least 20 representative questions, including paraphrases, unknowns, and adversarial wording.

Document the algorithm, scoring, limitations, and the measurable trigger for considering embeddings in `docs/KNOWLEDGE_MODEL.md`.

Tests must cover exact match, alias match, page-context boost, permission filtering, deprecated exclusion, unknown feature, deterministic ordering, malicious source text, and no-source behavior.

Run all quality gates and the retrieval evaluation command. End with summary, metrics, assumptions, failure cases, risks, and handoff to Prompt 13. Do not claim retrieval quality beyond measured fixtures.
```

### Files expected to be created or modified
- `src/orkafin/application/retrieval/**`
- retrieval evaluation fixtures/scripts
- `docs/KNOWLEDGE_MODEL.md`
- unit/integration/security tests

### Required tests
- Exact/alias/context retrieval.
- Permission filtering.
- Unknown and deprecated content.
- Deterministic ranking.
- Injection text treated as data.
- Source reference completeness.

### Verification commands
```bash
python -m orkafin.knowledge.evaluate
ruff format --check .
ruff check .
mypy src
pytest -q
```

### Acceptance criteria
- Known V1 questions retrieve the expected approved sources.
- Unknown features produce no source.
- Every grounded answer can cite an internal source reference.
- Retrieval remains deterministic and inspectable.

### Explicit non-goals
- No embeddings.
- No external model call.
- No internet search.
- No live Google Drive ingestion.

### Pass to the next prompt
- Retrieval service API.
- Evaluation score and failed cases.
- Source reference format.
- Deterministic intent labels.

### Suggested Git commit message
`feat: add deterministic approved-source retrieval`

---

## Prompt 13 — Add Provider-Independent AI Interface and Deterministic Provider

**Status:** Mandatory.

### Objective
Create an AI provider abstraction, a deterministic provider for all tests/offline use, and an optional external provider that cannot bypass grounding.

### Why this comes now
Retrieval is already authoritative. The provider can now improve phrasing while remaining downstream of trusted context and approved sources.

### Prerequisites
- Prompt 12 retrieval passes evaluation.
- Assistant response schema exists.

### Exact copy-paste prompt for the coding agent

```text
Implement the provider-independent response generation layer.

Inspect current schemas, retrieval service, configuration, errors, and docs before editing. Preserve all public interfaces. Do not embed provider-specific code in retrieval, permissions, adapters, or API routes.

Constraints:
- Deterministic provider is the default and must support all tests and the complete local demo.
- External provider is optional and disabled without configuration.
- A provider never decides permissions, available features, action success, or candidate visibility.
- A response cannot be marked grounded unless one or more approved sources were supplied and cited.
- Secrets remain server-side and are never logged or returned.
- No LangChain, LangGraph, or multi-agent framework.

Define a typed `ResponseProvider` interface that receives only:
- user question;
- safe resolved context summary;
- approved retrieved sources;
- explicit response intent;
- safe response constraints.

Implement:
1. `DeterministicResponseProvider` that formats explain-page, available-actions guidance, step-by-step help, candidate summary, refusal, unknown, and uncertainty responses using templates.
2. Optional external provider adapter selected by environment configuration. Choose one provider implementation only if the repository already has a preference; otherwise implement a generic OpenAI-compatible or Gemini adapter behind the interface, but keep it minimal and fully mocked in tests.
3. Structured provider output validation against `AssistantResponse` or an internal draft schema.
4. Timeout, malformed output, missing citation, and provider-error fallback to deterministic safe output.
5. Token/input minimization: send only retrieved excerpts and redacted context, never raw database rows, hidden fields, candidate notes, secrets, or full audit logs.

Add `docs/AI_PROVIDER_MODEL.md` documenting trust boundaries, input allowlist, fallback behavior, and why the model is optional.

Tests must prove:
- deterministic output is stable;
- no-source answers cannot claim grounding;
- provider output that invents a feature is rejected or downgraded;
- missing/unknown citations are rejected;
- provider errors fall back safely;
- secrets and redacted fields never enter provider payloads;
- no live network call occurs in tests.

Run all quality gates. End with files, commands/results, assumptions, unresolved risks, and handoff to Prompt 14. Do not claim an external provider is production-ready.
```

### Files expected to be created or modified
- `src/orkafin/providers/**`
- response generation service
- provider config
- `docs/AI_PROVIDER_MODEL.md`
- provider contract and security tests

### Required tests
- Deterministic stability.
- Grounding enforcement.
- Citation allowlist.
- Provider failure fallback.
- Payload minimization.
- No network in tests.

### Verification commands
```bash
ruff format --check .
ruff check .
mypy src
pytest -q tests/unit tests/security
pytest -q
```

### Acceptance criteria
- Local V1 works with no model key.
- Provider-specific logic is isolated.
- External provider cannot create new features or permissions.
- Grounding status is mechanically validated.

### Explicit non-goals
- No model fine-tuning.
- No conversation memory in model context beyond bounded messages.
- No provider benchmarking or multi-provider routing.

### Pass to the next prompt
- Provider interface.
- Deterministic template IDs.
- External provider config names.
- Fallback/error behavior.

### Suggested Git commit message
`feat: add provider-independent grounded response generation`

---

## Prompt 14 — Harden Prompt Contracts, Hallucination Controls, and Injection Defenses

**Status:** Mandatory — human security review required before Prompt 15.

### Objective
Formalize prompt templates, output contracts, trust labels, and adversarial defenses before exposing the assistant endpoint.

### Why this comes now
The provider exists but is not yet publicly reachable. This is the right moment to prevent untrusted content from steering the model or response contract.

### Prerequisites
- Provider abstraction and deterministic provider.
- Retrieval source model.
- Threat model.

### Exact copy-paste prompt for the coding agent

```text
Harden OrkaFin's prompt and response contracts against hallucination and prompt injection.

Inspect the provider layer, retrieval service, domain schemas, threat model, and tests before editing. Preserve established interfaces and document any intentional version change.

Security principles:
- System/developer rules outrank all retrieved and user-provided text.
- Retrieved help text and candidate fields are data, not instructions.
- Candidate notes are excluded by default. If a future path includes them, they must be explicitly labeled untrusted and never authorize actions.
- The model may summarize only supplied facts and may recommend only catalogued features/actions that pass permission checks.
- The model cannot claim an action succeeded; only an adapter execution receipt can do that.
- Unknown or insufficiently verified content must produce a safe unavailable/uncertain response.

Implement:
1. Versioned prompt templates separated by intent.
2. A compact trust-tagged context format with sections for verified context, approved sources, untrusted user question, and forbidden behaviors.
3. An output validator that allowlists source IDs, feature IDs, action IDs, and response kinds.
4. A claim/grounding check sufficient for V1: every factual feature/help claim must map to an approved source; candidate factual output must map to the adapter summary source.
5. Rejection/downgrade behavior for invented features, unsupported steps, unauthorized action suggestions, unknown source IDs, or success claims without receipts.
6. A bounded conversation-history policy that excludes hidden prompts and sensitive fields.
7. Red-team fixtures containing prompt injection in user questions, help documents, candidate notes, and prior assistant messages.

Do not rely on a keyword blacklist as the primary defense. Use trust boundaries, allowlists, minimal inputs, structured outputs, and post-validation.

Update `docs/THREAT_MODEL.md`, `docs/SECURITY_MODEL.md`, and provider docs with controls and residual risks.

Tests must cover:
- “ignore previous instructions” in user text;
- malicious help article attempting data exfiltration;
- malicious candidate note requesting admin behavior;
- invented OrkaATS feature;
- fake citation;
- unauthorized action suggestion;
- fabricated success;
- oversized input and history truncation;
- deterministic safe fallback.

Run all quality gates. Stop for human security review. Report every residual risk honestly. End with summary, files, test results, assumptions, and handoff to Prompt 15. Do not claim the system is secure merely because tests pass.
```

### Files expected to be created or modified
- `src/orkafin/providers/prompts/**`
- output validation/grounding modules
- red-team fixtures
- `docs/THREAT_MODEL.md`
- `docs/SECURITY_MODEL.md`
- security tests

### Required tests
- Prompt-injection cases.
- Hallucinated feature/action cases.
- Citation allowlist.
- No success without receipt.
- History/input limits.
- Safe fallback.

### Verification commands
```bash
ruff format --check .
ruff check .
mypy src
pytest -q tests/security
pytest -q
```

### Acceptance criteria
- Model output cannot bypass approved IDs or trusted context.
- Injection content is treated as data.
- Fabricated features and success messages are blocked.
- Human reviewer accepts residual risk documentation.

### Explicit non-goals
- No claim of complete prompt-injection prevention.
- No autonomous tool use.
- No model retraining.

### Pass to the next prompt
- Prompt template versions.
- Output validator interface.
- Allowed response kinds/IDs.
- Residual risks and security review notes.

### Suggested Git commit message
`security: enforce grounded prompt and output contracts`

---

# Phase 5 — Assistant API and Widget

## Prompt 15 — Implement Assistant, Conversation, Candidate Summary, and Guidance APIs

**Status:** Mandatory.

### Objective
Expose the core local V1 flows through a coherent versioned API.

### Why this comes now
Context, retrieval, provider, permissions, persistence, and guardrails are all ready. The API can now orchestrate them without becoming the source of business logic.

### Prerequisites
- Prompts 1–14 complete and reviewed.

### Exact copy-paste prompt for the coding agent

```text
Implement the OrkaFin Local V1 assistant API and conversation orchestration.

Inspect all existing routes, schemas, services, docs, and git status first. Preserve public interfaces. Keep API routes thin; do not duplicate permission, retrieval, adapter, or provider logic in controllers.

Required endpoints, with improved naming if documented consistently:
- GET /health
- GET /api/v1/apps/{app_id}/metadata
- POST /api/v1/contexts:resolve
- POST /api/v1/assistant/queries
- GET /api/v1/apps/{app_id}/features
- GET /api/v1/conversations/{conversation_id}

The assistant query flow must:
1. validate request and bounded question length;
2. resolve or revalidate trusted context for the request;
3. create/load a conversation owned by the verified local user/workspace;
4. retrieve approved sources;
5. optionally retrieve a permission-safe candidate summary from the adapter;
6. generate and post-validate a response;
7. persist user and assistant messages without raw hidden prompts or secrets;
8. attach request ID, grounding status, and sources;
9. audit sensitive candidate reads and permission denials;
10. return safe refusal/unavailable messages for missing identity, context, permission, source, or adapter failure.

Support these V1 flows:
- Explain this page.
- What can I do here?
- OrkaATS feature question.
- Step-by-step guidance.
- Candidate summary with permitted fields only.
- Basic next-step guidance based on verified page/stage rules.
- Unknown feature safe response.

Do not expose audit search to ordinary users. If an audit endpoint exists later, it must require a trusted local admin fixture and return redacted records.

Add API documentation with sample requests/responses for success, no context, no permission, unknown feature, unverified identity, and adapter failure.

Tests must cover full orchestration, conversation ownership, candidate redaction, source references, unknown questions, adapter errors, no fabricated success, request IDs, and persistence.

Run database migrations and all quality gates. Use the deterministic provider for acceptance tests. End with summary, files, commands/results, assumptions, unresolved risks, and handoff to Prompt 16. Do not claim completion if any endpoint test fails.
```

### Files expected to be created or modified
- assistant and app API routers
- orchestration services
- conversation repositories/services
- `docs/API.md`
- integration/e2e tests

### Required tests
- Core assistant intents.
- Candidate summary visibility.
- Conversation ownership/isolation.
- Source-aware responses.
- Safe unknown/refusal/failure behavior.
- Persistence and request IDs.

### Verification commands
```bash
alembic upgrade head
ruff format --check .
ruff check .
mypy src
pytest -q
uvicorn orkafin.main:app --reload
```

### Acceptance criteria
- Core local V1 questions work through API with deterministic provider.
- Every grounded response includes approved internal sources.
- Candidate data is adapter-provided and redacted.
- Unknowns and failures are honest and safe.

### Explicit non-goals
- No recommendations endpoint yet.
- No feedback endpoint yet.
- No action execution.
- No audit dashboard.

### Pass to the next prompt
- Final endpoint paths.
- Example payloads.
- Conversation/message schemas.
- Static demo base URL and CORS requirements.

### Suggested Git commit message
`feat: expose grounded OrkaFin assistant API`

---

## Prompt 16 — Build the Reusable Assistant Widget and Local Demo Harness

**Status:** Mandatory.

### Objective
Create a small, accessible, framework-free assistant panel that can later be embedded in an Apps Script HTML app.

### Why this comes now
The backend contract is stable enough to build against. Building the widget earlier would have encouraged fake client-side permissions and hard-coded responses.

### Prerequisites
- Assistant API works end-to-end.

### Exact copy-paste prompt for the coding agent

```text
Build the reusable OrkaFin assistant widget and a local OrkaATS demo harness.

Inspect current web assets, API docs, CORS settings, and repository conventions before editing. Preserve existing functionality. Do not add React/Vue/Svelte or another heavy framework; plain HTML, CSS, and JavaScript are sufficient.

Requirements:
- Separate UI rendering, state management, and transport modules.
- No secrets in frontend code.
- No client-side role/permission authority. The demo may select a fixture identity token/header, but label it as local test mode and let the backend resolve permissions.
- Use `textContent` and safe DOM creation; do not render model output with unsafe `innerHTML`.
- Accessible keyboard navigation, focus handling, labels, status announcements, and reasonable contrast.
- Responsive compact panel suitable for later Apps Script embedding.

Build:
1. Bottom-right launcher and compact assistant panel.
2. Demo controls for current page and selected synthetic candidate.
3. Typed question input and send state.
4. Suggested prompts: Explain this page, What can I do here?, Summarize this candidate, Recommend a useful feature.
5. Rendering for explanation, steps, candidate summary, sources, refusals, uncertainty, errors, and request ID.
6. Conversation reset.
7. Loading, empty, offline, timeout, and adapter failure states.
8. A transport configuration that supports local API base URL and can later be replaced for Apps Script embedding.
9. A local demo page served by FastAPI or a documented static server.

Do not implement voice, video, file upload, rich Markdown, or action confirmation yet.

Add browser-level tests with the lightest practical tool already available. If no browser automation is installed, add DOM unit tests plus one documented manual smoke test; do not pull in a huge stack without justification.

Update docs with embed constraints, CORS, local run steps, and screenshots only if generated from the working UI.

Tests must cover suggested prompt dispatch, safe text rendering, candidate selection context, refusal display, source display, API error handling, and no secret/config leakage.

Run all backend and frontend checks. End with summary, files, commands/results, assumptions, risks, and handoff to Prompt 17. Do not claim Apps Script embedding is complete; only that the component is designed for it.
```

### Files expected to be created or modified
- `src/orkafin/web/**`
- static route/demo page
- frontend tests
- `docs/LOCAL_SETUP.md`
- `docs/ORKA_ATS_ADAPTER_CONTRACT.md` embed notes

### Required tests
- Safe DOM rendering.
- Suggested prompts.
- Context submission.
- Error/refusal/source rendering.
- No secrets in bundled/static files.

### Verification commands
```bash
ruff format --check .
ruff check .
mypy src
pytest -q
uvicorn orkafin.main:app --reload
# Open the documented local demo URL and run the smoke checklist.
```

### Acceptance criteria
- Local user can select a page/candidate and ask core questions.
- Widget is reusable and transport is replaceable.
- UI does not trust or expose permissions/secrets.
- Core flows are accessible and safe against HTML injection.

### Explicit non-goals
- No voice.
- No production Apps Script deployment.
- No complex design system.
- No action controls yet.

### Pass to the next prompt
- Demo URL.
- Widget module/initialization API.
- Transport interface.
- Manual smoke-test results.

### Suggested Git commit message
`feat: add reusable local OrkaFin assistant widget`

---

# Phase 6 — Recommendations, Events, and Feedback

## Prompt 17 — Add Meaningful Events, Rule-Based Recommendations, Rate Limits, and Feedback

**Status:** Mandatory.

### Objective
Implement explainable feature recommendations based on explicit rules, meaningful event logs, and user feedback with suppression behavior.

### Why this comes now
The assistant works. Recommendations can now be added without pretending V1 “learns” through model retraining. Events and feedback create the data foundation for future personalization.

### Prerequisites
- Persistence, context, assistant API, and widget.
- Recommendation catalog from Prompt 6.

### Exact copy-paste prompt for the coding agent

```text
Implement meaningful event logging, deterministic recommendation evaluation, feedback capture, and recommendation suppression.

Inspect existing persistence models, knowledge rules, APIs, widget, and docs before editing. Preserve interfaces. Do not introduce ML, continuous retraining, clickstream tracking, or a generic analytics dashboard.

Event rules:
- Log meaningful business/product events only: app/page opened, candidate selected, assistant query submitted, recommendation shown, accepted, dismissed, feedback submitted, action proposed/confirmed/succeeded/failed.
- Do not log every click, keystroke, full question text when unnecessary, candidate notes, secrets, or hidden fields.
- Use validated event types and bounded metadata.

Recommendation engine:
- Use version-controlled rules from `knowledge/orka_ats/recommendations.yaml`.
- Evaluate trusted page, verified permissions, approved features, and recent meaningful events.
- Recommendations must cite the feature/rule source and explain why they were shown.
- Do not recommend inaccessible features or actions.
- Add frequency limits, such as one impression per rule/user/workspace within a configurable window.
- After dismissal, suppress the same rule for a longer configurable period.
- After acceptance, mark it accepted and avoid repeating unless the rule explicitly allows recurrence.
- Provide an opt-out or reduced-recommendation preference in local fixture settings.

Add endpoints with consistent naming, for example:
- POST /api/v1/events
- POST /api/v1/recommendations:evaluate
- POST /api/v1/feedback

Feedback types must include helpful, not_helpful, accepted, dismissed, with validation linking feedback to a message or recommendation.

Update the widget to display a recommendation card, reason, source, accept/dismiss controls, and suppression result. Keep proactive behavior non-annoying: do not auto-pop the panel repeatedly.

Tests must cover accepted/dismissed feedback, repeated recommendation suppression, opt-out, permission filtering, unknown rule references, event metadata validation, PII exclusion, and deterministic recommendation results.

Update `docs/EVENT_AND_AUDIT_MODEL.md`, `docs/KNOWLEDGE_MODEL.md`, and `docs/TEST_STRATEGY.md`.

Run migrations, knowledge validation, all tests, Ruff, and mypy. End with summary, measured rule behavior, assumptions, risks, and handoff to Prompt 18 or Prompt 20 if the action POC is skipped.
```

### Files expected to be created or modified
- event/recommendation/feedback services and endpoints
- recommendation rule catalog
- persistence migration if needed
- widget recommendation UI
- docs and tests

### Required tests
- Rule matching and permission filtering.
- Accept/dismiss/helpful/not-helpful capture.
- Impression and dismissal suppression.
- Recommendation opt-out.
- Event allowlist/metadata bounds.
- Sensitive-data exclusion.

### Verification commands
```bash
alembic upgrade head
python -m orkafin.knowledge.validate knowledge/orka_ats
ruff format --check .
ruff check .
mypy src
pytest -q
```

### Acceptance criteria
- At least one useful OrkaATS feature recommendation is explainable and source-backed.
- Repeated suggestions are suppressed correctly.
- Users can dismiss/disable recommendations.
- Events are meaningful and privacy-minimized.

### Explicit non-goals
- No ML recommendation model.
- No cross-app recommendations in the pilot.
- No full analytics dashboard.
- No automatic workflow creation.

### Pass to the next prompt
- Event type list.
- Recommendation rule IDs.
- Frequency/suppression defaults.
- Feedback endpoint and schema.
- Decision whether to include optional action POC.

### Suggested Git commit message
`feat: add explainable recommendations events and feedback`

---

# Phase 7 — Confirmed Action Proof of Concept

## Prompt 18 — Define Action Catalog, Proposal, Confirmation, and Audit State

**Status:** Optional V1 extension — human review required before Prompt 19.

### Objective
Implement the safe preparation and confirmation state machine for one low-risk action without executing it yet.

### Why this comes now
Action execution is the riskiest V1 feature. Proposal, confirmation, permissions, audit, expiry, and replay protection must exist before the adapter can change state.

### Prerequisites
- Prompts 1–17 complete.
- Human decision to include action POC.
- Approved action selected. Recommended: `candidate.update_start_date` in mock mode only, because it is bounded, reversible, and demonstrates a real state change. Replace only if OrkaATS leadership chooses a safer field.

### Exact copy-paste prompt for the coding agent

```text
Implement the action catalog, proposal, preview, confirmation, and audit state machine for one approved mock OrkaATS action. Do not execute the action yet.

Inspect all existing domain models, permissions, adapters, persistence, knowledge actions, threat model, and docs before editing. Preserve public interfaces. Do not introduce a generic arbitrary tool executor.

Selected action:
- Use the human-approved low-risk action. Default only if no alternative was approved: `candidate.update_start_date`.
- It must be defined in the versioned action catalog with owning app, required permission, input schema, validation, confirmation requirement, reversibility, sensitive classification, audit fields, and failure behavior.

Implement:
1. Action proposal service that verifies trusted identity/context, action catalog membership, target visibility, required permission, input validation, and adapter availability.
2. A preview containing what changes, owning app, target candidate ID, old/new safe values, affected user/workspace, reversibility, and warnings.
3. Persistent proposal state with parameter hash, request ID, expiration, status, and idempotency key.
4. One-time confirmation tokens generated with secure randomness, stored only as hashes, bound to user/workspace/proposal/parameter hash, and expiring after configured TTL.
5. Separate confirmation state from execution state.
6. Audit records for proposal, permission check, confirmation issued, confirmation accepted/rejected/expired, and tampering attempts.
7. Endpoints such as:
   - POST /api/v1/action-proposals
   - POST /api/v1/action-proposals/{proposal_id}/confirmations

The confirmation endpoint must not execute the action yet. It should only validate intent and produce an execution-ready state.

Tests must cover missing permission, invisible candidate, invalid date/value, tampered parameters, expired token, reused token, wrong user/workspace, already-cancelled proposal, adapter unavailable, and audit creation. Logs and responses must not expose token hashes or hidden candidate data.

Create/refine `docs/ACTION_AND_CONFIRMATION_FLOW.md` with a state diagram and threat controls. Update the widget with preview/confirm/cancel UI, but keep execution disabled and label it clearly.

Run migrations and all quality gates. Stop for human review of the exact preview, token binding, audit records, and selected action. End with summary, files, results, assumptions, residual risks, and handoff to Prompt 19. Do not claim any state change was executed.
```

### Files expected to be created or modified
- action catalog entry
- proposal/confirmation services and endpoints
- persistence migration
- widget preview/confirm/cancel UI
- `docs/ACTION_AND_CONFIRMATION_FLOW.md`
- action/security tests

### Required tests
- Proposal permission and visibility.
- Input validation.
- Token expiry/reuse/tampering.
- User/workspace binding.
- Audit events.
- No execution occurs.

### Verification commands
```bash
alembic upgrade head
python -m orkafin.knowledge.validate knowledge/orka_ats
ruff format --check .
ruff check .
mypy src
pytest -q tests/security tests/integration
pytest -q
```

### Acceptance criteria
- Only catalogued action can be proposed.
- Confirmation is one-time, expiring, and bound to exact parameters/user/workspace.
- No state change occurs in this prompt.
- Human reviewer approves before execution is added.

### Explicit non-goals
- No real Apps Script execution.
- No destructive actions.
- No multi-action plans.
- No autonomous confirmation.

### Pass to the next prompt
- Approved action ID and input schema.
- Proposal/confirmation endpoints.
- TTL and idempotency design.
- Human review approval and residual risks.

### Suggested Git commit message
`feat: add audited action proposal and confirmation state`

---

## Prompt 19 — Execute One Approved Action Through the Mock Adapter

**Status:** Optional V1 extension.

### Objective
Complete one end-to-end, permission-revalidated, confirmed action through the mock OrkaATS adapter with honest success/failure handling.

### Why this comes now
Execution is last because all safety mechanisms are already in place. This prompt proves the architecture without turning OrkaFin into an unrestricted automation engine.

### Prerequisites
- Prompt 18 human-approved.
- Mock adapter has isolated mutable state and reset behavior.

### Exact copy-paste prompt for the coding agent

```text
Implement execution of the single approved action through the mock OrkaATS adapter.

Inspect all action state, adapter contracts, permissions, audits, docs, and tests before editing. Preserve interfaces. Do not add additional actions or a generic tool runner.

Execution requirements:
1. Accept only a valid execution-ready proposal and one-time confirmed state.
2. Re-resolve trusted identity and context at execution time.
3. Re-check candidate visibility, action permission, current candidate state, action definition version, and parameter hash.
4. Reject execution if permissions changed after proposal, candidate state conflicts, token expired/reused, action version changed, or adapter is unavailable.
5. Send a versioned `execute_approved_action` request to the mock adapter with request ID and idempotency key.
6. The mock adapter validates business rules again and returns a typed execution receipt.
7. Mark success only when a valid receipt is returned.
8. Persist execution outcome and append audit records for attempt, permission recheck, adapter request, success/failure, and final safe result.
9. On timeout or ambiguous failure, do not retry blindly. Return an unknown/failed state that can be reconciled by idempotency key.
10. Prevent duplicate execution when the same confirmation or idempotency key is reused.

Add an endpoint such as:
- POST /api/v1/action-proposals/{proposal_id}:execute

Update the widget so the final execution requires an explicit user click after preview/confirmation. Display adapter-confirmed success or the safe message: “OrkaATS could not complete the request. No changes were made.” For ambiguous timeout, do not assert that no change occurred unless the adapter can prove it; use a reconciliation-safe message.

Implement mock-state rollback/reset for tests. If the selected action is reversible, document a manual compensating operation, but do not build a general rollback engine.

Tests must cover success, permission revoked between proposal and execution, candidate changed between steps, adapter validation error, timeout, malformed receipt, duplicate execution, reused confirmation, idempotent replay, audit creation, and no fabricated success.

Update action flow, adapter contract, threat model, and test strategy docs. Run full quality gates and local end-to-end action demo. End with exact results, residual risks, assumptions, and handoff to Prompt 20. Do not claim real OrkaATS integration has been proven.
```

### Files expected to be created or modified
- action execution service/endpoint
- mock adapter action implementation
- isolated mock state/reset utility
- widget execution result UI
- docs and action/security/e2e tests

### Required tests
- Successful execution with receipt.
- Permission change between phases.
- State conflict.
- Timeout/malformed receipt.
- Duplicate/idempotent behavior.
- No fabricated success.
- Audit completeness.

### Verification commands
```bash
python -m orkafin.adapters.orka_ats.seed --reset
alembic upgrade head
ruff format --check .
ruff check .
mypy src
pytest -q
```

### Acceptance criteria
- Exactly one action works end-to-end in mock mode.
- Permission and state are revalidated at execution.
- Success requires a valid adapter receipt.
- Duplicate/replay attempts are safe.
- Real Apps Script execution is still explicitly unproven.

### Explicit non-goals
- No additional actions.
- No real candidate Sheet update.
- No background actions.
- No cross-app workflow.

### Pass to the next prompt
- Action demo steps.
- Execution endpoint and receipt schema.
- Idempotency/reconciliation behavior.
- Residual risks and known unsupported cases.

### Suggested Git commit message
`feat: execute one confirmed action through mock OrkaATS`

---

# Phase 8 — Security and QA

## Prompt 20 — Run Security Hardening, Adversarial Tests, and Full Regression

**Status:** Mandatory whether or not optional action prompts were run.

### Objective
Consolidate the quality bar into a full security, permission-leakage, hallucination, failure, and regression suite.

### Why this comes now
Feature work is complete. The system needs adversarial verification across module boundaries, not just unit tests written by the same prompt that built each feature.

### Prerequisites
- Prompts 1–17 complete.
- Prompts 18–19 either complete or explicitly skipped.

### Exact copy-paste prompt for the coding agent

```text
Perform a security and QA hardening pass for OrkaFin Local V1. Do not add new product features.

Inspect the entire repository, test suite, threat model, decisions, and git history first. Preserve working functionality. Fix defects with the smallest compatible change. Do not weaken tests to make them pass.

Create a traceable test matrix covering:
- schema validation;
- context validation;
- forged client role/email/permissions/actions;
- missing or unverified identity;
- candidate record visibility;
- field-level redaction;
- approved feature/help retrieval;
- source-aware answers;
- unknown questions/features;
- hallucinated features and fake citations;
- prompt injection in user questions, help docs, candidate notes, and conversation history;
- recommendation acceptance/dismissal and repeated suppression;
- recommendation opt-out;
- confirmation required before actions, if action POC exists;
- expired/reused/tampered confirmation, if applicable;
- permission changes between proposal and execution, if applicable;
- adapter timeout, malformed response, conflict, and unavailable errors;
- no fabricated success;
- audit creation and append-only behavior;
- sensitive-data exclusion from logs, messages, events, and audit payloads;
- CORS and error envelope;
- conversation isolation;
- end-to-end local assistant flow.

Add property-based tests only where they produce real value, such as ID/input bounds or redaction invariants. Do not introduce a large dependency without justification.

Run dependency vulnerability scanning if a lightweight tool is already configured. Otherwise document the exact recommended command and do not invent results. Add a secret scan of the repository using available tooling or robust grep patterns.

Add coverage reporting and set a pragmatic threshold focused on critical modules rather than chasing a vanity percentage. Report uncovered critical paths explicitly.

Create/refine `docs/TEST_STRATEGY.md` with:
- test pyramid;
- contract/integration/security/e2e responsibilities;
- fixture reset strategy;
- no-live-network rule;
- release gate commands;
- known residual risks.

Fix all discovered defects, update ADRs only if architecture changes, and run the full release gate from a clean database and reset mock adapter state.

Do not claim the system is “secure” or “production-ready.” State only what was tested. End with defects found/fixed, commands/results, coverage, skipped tests with reasons, residual risks, and handoff to Prompt 21.
```

### Files expected to be created or modified
- `tests/security/**`
- `tests/integration/**`
- `tests/e2e/**`
- coverage/tool config
- `docs/TEST_STRATEGY.md`
- targeted bug fixes

### Required tests
- Entire testing quality bar from the project brief.
- Clean-state migration and seed.
- No-live-network test enforcement.
- Secret and sensitive-data checks.

### Verification commands
```bash
rm -f var/orkafin.db
python -m orkafin.adapters.orka_ats.seed --reset
alembic upgrade head
python -m orkafin.knowledge.validate knowledge/orka_ats
ruff format --check .
ruff check .
mypy src
pytest --cov=orkafin --cov-report=term-missing -q
```

### Acceptance criteria
- Full release gate passes from clean state.
- Critical security tests exist and are traceable to threats.
- No test relies on a live AI provider or live Apps Script service.
- Residual risks are documented honestly.

### Explicit non-goals
- No penetration-test claim.
- No production compliance certification.
- No new product features.
- No cloud load testing.

### Pass to the next prompt
- Release-gate commands and results.
- Coverage and critical gaps.
- Known residual risks.
- Whether optional action POC is included.
- Any manual tests still required.

### Suggested Git commit message
`test: harden OrkaFin security and regression coverage`

---

# Phase 9 — End-to-End Demo and Documentation

## Prompt 21 — Package the Local Demo, Runbook, Onboarding Guide, and Final Acceptance

**Status:** Mandatory — final human acceptance required.

### Objective
Make the repository usable by another developer from a fresh clone and document exactly how OrkaATS and future Orka apps will integrate later.

### Why this comes last
Documentation written before the system works becomes fiction. This prompt validates the actual repository and records the proven path, limitations, and migration boundaries.

### Prerequisites
- Prompt 20 release gate passes.

### Exact copy-paste prompt for the coding agent

```text
Finalize OrkaFin Local V1 as a reproducible local demo and developer handoff. Do not add new product features.

Inspect the complete repository, all docs, tests, and git status first. Preserve working behavior. Remove only dead code that is proven unused and covered by tests. Do not rewrite stable interfaces for cosmetic reasons.

From a clean state, verify that a developer can:
1. clone the repository;
2. create a virtual environment;
3. install dependencies;
4. copy `.env.example` safely;
5. initialize SQLite through Alembic;
6. validate/load OrkaATS starter knowledge;
7. reset/seed mock OrkaATS fixtures;
8. start FastAPI;
9. open the local widget;
10. choose a mock page and candidate;
11. ask page/feature/help questions;
12. receive grounded sources;
13. receive permission-safe candidate summaries;
14. receive unknown/refusal/failure messages;
15. view a basic recommendation;
16. submit helpful/not-helpful/accepted/dismissed feedback;
17. inspect local event and redacted audit records through a safe developer command;
18. optionally propose, confirm, and execute the single mock action if included;
19. run the complete release gate successfully.

Create or refine:
- README.md
- docs/LOCAL_SETUP.md
- docs/DEVELOPER_RUNBOOK.md
- docs/LOCAL_DEMO.md
- docs/API.md
- docs/ORKA_APP_ONBOARDING_GUIDE.md
- docs/FUTURE_MIGRATION_PLAN.md
- docs/V1_ACCEPTANCE_CHECKLIST.md
- docs/DECISIONS.md

The onboarding guide must explain how a future Orka app implements the general adapter without giving OrkaFin direct database access. Include contract tests, versioning, identity assertions, permission checks, source catalogs, action receipts, and audit integration.

The migration plan must distinguish:
- local mock mode;
- controlled tunnel testing;
- hosted API prerequisites;
- production identity/authentication;
- secrets management;
- managed database migration;
- observability;
- background processing only when justified;
- data retention and incident response;
- what must remain inside OrkaATS.

Add sample requests/responses that use synthetic data only. Add a one-command or short-command demo script that checks prerequisites and refuses unsafe configuration. Add a developer CLI to inspect redacted events/audits instead of exposing an unrestricted public endpoint.

Run the complete clean-state setup exactly as documented. Correct any inaccurate instructions. Record real command outputs, not assumptions. Create a final acceptance report listing pass/fail for every V1 target and every deliberately deferred feature.

Do not claim production readiness. End with:
- final architecture summary;
- exact setup/demo/release commands;
- acceptance results;
- optional action status;
- unresolved risks;
- required work before live OrkaATS data or deployment;
- recommended next V2 milestone.
```

### Files expected to be created or modified
- `README.md`
- `docs/LOCAL_SETUP.md`
- `docs/DEVELOPER_RUNBOOK.md`
- `docs/LOCAL_DEMO.md`
- `docs/API.md`
- `docs/ORKA_APP_ONBOARDING_GUIDE.md`
- `docs/FUTURE_MIGRATION_PLAN.md`
- `docs/V1_ACCEPTANCE_CHECKLIST.md`
- demo/inspection scripts
- any small fixes found during clean setup

### Required tests
- Clean clone/setup simulation.
- Full release gate.
- End-to-end widget flow.
- Optional action demo if included.
- Documentation command accuracy.

### Verification commands
```bash
rm -rf .venv var/orkafin.db
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
alembic upgrade head
python -m orkafin.knowledge.validate knowledge/orka_ats
python -m orkafin.adapters.orka_ats.seed --reset
ruff format --check .
ruff check .
mypy src
pytest --cov=orkafin --cov-report=term-missing -q
uvicorn orkafin.main:app --reload
```

### Acceptance criteria
- A second developer can reproduce the demo from documentation.
- All 20 final acceptance targets are marked with evidence.
- Mock-to-real adapter replacement is understandable.
- Future Orka app onboarding is documented.
- Production gaps are explicit, not hidden.

### Explicit non-goals
- No cloud deployment.
- No production OAuth.
- No live OrkaATS candidate data.
- No V2 features disguised as cleanup.

### Pass to the next prompt
There is no implementation prompt after this one. Pass the final acceptance report, unresolved risks, and recommended V2 backlog to the human project lead.

### Suggested Git commit message
`docs: finalize OrkaFin local V1 demo and acceptance runbook`

---

# Human Checkpoints

## Checkpoint A — After Prompt 1
Approve:
- local-only boundary;
- one-service architecture;
- OrkaATS ownership;
- no vector database;
- optional model provider;
- no direct Sheet access.

## Checkpoint B — After Prompt 7
Approve:
- fixture roles and permissions;
- candidate record visibility;
- field-level redaction;
- treatment of notes;
- local identity disclaimer.

## Checkpoint C — After Prompt 11
Approve:
- trusted versus untrusted context;
- context API response;
- candidate-read audits;
- denial behavior.

## Checkpoint D — After Prompt 14
Approve:
- prompt/output contract;
- hallucination controls;
- injection defenses;
- residual security risks.

## Checkpoint E — Before Prompt 19
Approve:
- whether an action POC belongs in V1;
- exact action and field;
- confirmation preview;
- token binding and TTL;
- audit records;
- rollback/compensation expectations.

## Checkpoint F — After Prompt 21
Approve:
- release-gate evidence;
- local demo;
- known limitations;
- next V2 milestone.

---

# Dependency Map

```text
Prompt 1  Scope/architecture
   |
   v
Prompt 2  Repository scaffold
   |
   v
Prompt 3  Config/logging/errors/request IDs
   |
   +---------------------------+
   |                           |
   v                           v
Prompt 4  Domain contracts     Prompt 6 Knowledge catalogs
   |                           |
   v                           |
Prompt 5  OrkaFin persistence  |
   |                           |
   v                           |
Prompt 7  Identity/permissions/redaction
   |
   v
Prompt 8  General app adapter contract
   |
   v
Prompt 9  Mock OrkaATS adapter
   |
   +-------------> Prompt 10 Real Apps Script contract
   |
   v
Prompt 11 Trusted context resolution
   |
   +--------------------------+
   |                          |
   v                          v
Prompt 12 Structured retrieval <--- Prompt 6
   |
   v
Prompt 13 Provider abstraction/deterministic provider
   |
   v
Prompt 14 Prompt/output security
   |
   v
Prompt 15 Assistant API/conversations
   |
   v
Prompt 16 Reusable widget/demo
   |
   v
Prompt 17 Events/recommendations/feedback
   |
   +------------------------------+
   |                              |
   | Optional                     | Skip action POC
   v                              |
Prompt 18 Proposal/confirmation   |
   |                              |
   v                              |
Prompt 19 Mock action execution   |
   +--------------+---------------+
                  |
                  v
Prompt 20 Security/QA hardening
                  |
                  v
Prompt 21 Demo/runbook/final acceptance
```

---

# V1 Completion Checklist

## Mandatory product behavior
- [ ] Local FastAPI service starts without external AI credentials.
- [ ] Reusable framework-free assistant panel opens locally.
- [ ] User can choose a mock OrkaATS page and candidate.
- [ ] Client role/email/permission claims are not trusted.
- [ ] Trusted context is resolved through the adapter boundary.
- [ ] “Explain this page” works with approved sources.
- [ ] “What can I do here?” returns only catalogued, permitted features/actions.
- [ ] OrkaATS feature questions and verified steps are source-aware.
- [ ] Candidate summary includes only permitted fields.
- [ ] Missing candidate, missing permission, unverified identity, unknown feature, and adapter failure produce safe responses.
- [ ] Unknown questions do not produce invented features.
- [ ] Deterministic provider supports all tests and demo flows.
- [ ] External provider is optional and isolated.
- [ ] Meaningful events are persisted without unnecessary private content.
- [ ] Recommendation is rule-based, explainable, dismissible, and rate-limited.
- [ ] Helpful/not-helpful/accepted/dismissed feedback is stored.
- [ ] Sensitive reads and permission denials create redacted audit records.
- [ ] Full test suite passes from a clean database and reset fixtures.
- [ ] Real Apps Script adapter contract and limitations are documented.
- [ ] Future Orka app onboarding is documented.

## Optional action POC
- [ ] Exactly one action is catalogued.
- [ ] Proposal verifies permission and record visibility.
- [ ] Preview shows exact change.
- [ ] Confirmation is one-time, expiring, and parameter-bound.
- [ ] Permission and state are rechecked at execution.
- [ ] Success requires a valid adapter receipt.
- [ ] Replay, timeout, permission change, and conflict tests pass.
- [ ] No claim is made that real Apps Script execution works.

## Documentation and migration
- [ ] README and local setup work from a fresh clone.
- [ ] Architecture and ADRs match the implementation.
- [ ] Security and threat model list residual risk.
- [ ] Knowledge ownership/update process is documented.
- [ ] Production prerequisites are explicit.
- [ ] No prototype shortcut is presented as permanent production architecture.

---

# Deliberately Deferred Until V2 or Later

## V2 candidates
- Usage-informed recommendations across a larger event history.
- Additional OrkaATS features and authoritative stage/field sync.
- User preference UI beyond basic recommendation opt-out.
- Controlled Apps Script tunnel test with synthetic data.
- Richer screenshot/image help only after approved sources and privacy review.
- More robust audit review tooling for admins.

## V3/V4 candidates
- Additional confirmed actions.
- Task creation/assignment through the owning app.
- Candidate stage changes after business-rule review.
- Cross-app workflows.
- Background jobs only when a real asynchronous need exists.
- Hosted API with production authentication and managed secrets.

## V5 or later
- Cross-app intelligence across Orka OS.
- Long-term organizational memory.
- Voice input and voice summaries.
- Advanced automation discovery.
- Proactive productivity nudges.
- More sophisticated recommendation models.

## Explicitly not justified now
- Kubernetes.
- Multiple microservices.
- Kafka, Pub/Sub, or Redis.
- Dedicated vector database.
- LangGraph or multi-agent orchestration.
- Continuous model retraining.
- Tracking every click or keystroke.
- Large analytics dashboard.
- Direct access to every Orka Google Sheet.
- Autonomous state-changing actions.

---

# Final advisory note

The correct V1 is not “a chatbot that can answer things.” It is a narrow, permission-aware guidance system with trustworthy context, explicit knowledge, versioned adapters, honest uncertainty, and evidence-producing tests. The optional action is valuable only if it proves those boundaries. If it forces shortcuts, skip it. A secure guidance-only V1 is a real product increment; an impressive-looking action demo that trusts the browser or bypasses OrkaATS is technical debt disguised as progress.
