# Local V1 Decisions, Assumptions, and Open Questions

**Status:** Decision set frozen for Prompt 1 human review  
**Last updated:** 2026-07-13

## How to use this record

This file is the index of V1 architectural decisions and unresolved product/policy
choices. The linked ADRs explain high-impact decisions in depth. No later prompt
may silently replace these boundaries. Record approval, rejection, or requested
changes in the review record below before Prompt 2.

Precedence for Local V1 is:

1. Approved ADRs and this decision record.
2. `docs/ARCHITECTURE.md`, `docs/SECURITY_MODEL.md`, and the V1 scope.
3. The ordered implementation prompt pack for sequencing.
4. The broader ecosystem source context for future direction.

When two documents conflict, stop and reconcile them in writing.

The architecture decision records are:

- [ADR-001: local-first modular architecture](adr/ADR-001-local-first-architecture.md)
- [ADR-002: application data ownership](adr/ADR-002-application-data-ownership.md)
- [ADR-003: no vector database for initial V1](adr/ADR-003-no-vector-database-for-initial-v1.md)
- [ADR-004: provider-independent AI interface](adr/ADR-004-provider-independent-ai-interface.md)

## Frozen V1 decisions

| ID | Decision | Rationale/status |
|---|---|---|
| D-001 | OrkaATS is the sole V1 pilot. | Proves one end-to-end boundary before cross-app complexity. |
| D-002 | Use one local modular FastAPI service, not microservices. | Operationally simplest and sufficient for V1; see ADR-001. |
| D-003 | Package name is `orkafin`, using a `src` layout. | Provides an unambiguous Prompt 2 handoff; final directory details may be adapted compatibly. |
| D-004 | Support Python 3.11 or newer and target Python 3.11 semantics. | Matches the requested baseline without relying on newer-only behavior. |
| D-005 | Use Pydantic v2, SQLAlchemy 2, SQLite, and Alembic. | Typed contracts and real migration boundaries are warranted by persistent OrkaFin state. |
| D-006 | OrkaATS owns candidate records, permissions, business rules, validation, and writes. | Non-negotiable ownership boundary; see ADR-002. |
| D-007 | OrkaFin never directly reads or writes the OrkaATS Google Sheet. | All candidate interaction passes through a versioned adapter. |
| D-008 | OrkaFin persistence has no candidate table or durable candidate-row replica. | Prevents accidental shadow ownership. Mock adapter state is isolated. |
| D-009 | The public context request accepts only app/page navigation and optional entity selection; browser identity, role, permissions, workspace, request ID, and actions are forbidden. | Trusted facts are server/adapter resolved and request-scoped; invalid authority claims fail at validation. |
| D-010 | Local identities are explicit synthetic fixtures. | Useful for testing, but not production authentication. |
| D-011 | Future Orka apps implement a versioned general adapter contract. | Keeps core services application-neutral and preserves ownership. |
| D-012 | Initial retrieval is structured and deterministic. | Small approved corpus does not justify vector infrastructure; see ADR-003. |
| D-013 | A deterministic response provider is the default and supports all tests/demo. | Removes network/key dependency and gives repeatable behavior; see ADR-004. |
| D-014 | An external model may improve wording only from minimized grounded input. | Models do not decide permissions, features, actions, or success. |
| D-015 | Candidate notes are excluded from provider input by default and always treated as sensitive untrusted data. | Reduces leakage and stored prompt-injection risk. |
| D-016 | Guidance/recommendations are mandatory; action execution is optional. | Proves useful safe read behavior before write risk. |
| D-017 | If enabled, exactly one mock-only action requires proposal, preview, permission, one-time confirmation, revalidation, idempotency, audit, failure handling, and receipt. | No autonomous or generic action execution. |
| D-018 | The widget remains plain HTML, CSS, and JavaScript. | Sufficient for embedability and keeps local V1 small. |
| D-019 | No production cloud architecture or live Apps Script integration is claimed. | Apps Script server runtime cannot be assumed to reach developer localhost. |
| D-020 | Security-sensitive logs/audits store bounded structured facts, not raw bodies, notes, prompts, or secrets. | Minimizes secondary disclosure and replay risk. |
| D-021 | Domain wire contracts use strict Pydantic models with literal schema version `v1`, forbidden extra fields, UTC timestamps, and immutable code-owned data policies. | Makes version, ownership, sensitivity, and persistence expectations mechanically visible before adapters or storage exist. |
| D-022 | Canonical request and correlation IDs are lowercase UUID strings; app/catalog/action IDs use bounded explicit patterns; permissions are lowercase namespaced values. | Preserves Prompt 3 request-ID compatibility while preventing unbounded or ambiguous identifiers. |
| D-023 | `ClientContextHint` and `ResolvedPageContext` are incompatible types with fixed trust labels; the request has only navigation/selection fields, and public resolved identity omits verified email. | Prevents client navigation from being reinterpreted as adapter authorization, minimizes identity disclosure, and records the non-durable trust lifetime. |
| D-024 | `CandidateSummary` is a request-scoped typed OrkaATS view with visible fields and safe redaction counts, not a persistence model. Notes are absent by default; any future excerpt is permanently labeled sensitive and untrusted and is never persisted. | Implements D-006, D-008, and D-015 without deciding the unresolved field policy in Q-002. |
| D-025 | Assistant output uses closed response kinds with mechanical grounding rules, and successful action results require a matching owning-adapter receipt. | Makes unavailable/refusal behavior and the no-fabricated-success rule structural. |
| D-026 | The future OrkaATS Apps Script boundary uses wire schema `v1` over the unchanged general adapter contract `1.0.0`, through an injected transport. The shell is disabled by default, requires an explicit HTTPS endpoint and bounded timeout/response size, and contains no network client, URL, secret, or production authentication. | Makes HTTP replaceable and locally mockable without coupling core services or falsely claiming a secure live integration. |
| D-027 | Mock, browser-local, controlled HTTPS tunnel, and later hosted API are distinct integration modes. Browser claims remain untrusted; Apps Script server-side code cannot reach a developer laptop through `localhost`; a tunnel is synthetic-data-only temporary testing, not production architecture. | Prevents local connectivity techniques from being mistaken for identity proof, deployment, or an approved live data path. |

The Prompt 4 field shapes, module paths, ID patterns, and handling table are in
[`DOMAIN_MODEL.md`](DOMAIN_MODEL.md). These entries clarify existing boundaries;
they do not approve persistence, adapters, field permissions, or an executable
action.

## Repository layout assumption for Prompt 2

The approved starting assumption is one package under `src/orkafin` with internal
areas for `api`, `core`, `domain`, `application`, `adapters`, `infrastructure`,
`knowledge`, `providers`, and `web`, plus `tests/{unit,integration,security,e2e}`,
`knowledge/orka_ats`, `fixtures`, `scripts`, and `docs`. Empty ceremonial modules
are not required; Prompt 2 should create only the scaffold requested there.

Existing files to preserve compatibly are `AGENTS.md`, this documentation set, the
implementation prompt pack, the ecosystem source context, and `.gitignore`.
Currently no application interface exists to migrate.

## Explicit assumptions

These assumptions allow documentation and scaffolding to advance but must be
validated before the prompt noted.

| ID | Assumption | Validate by |
|---|---|---|
| A-001 | Synthetic OrkaATS data with no real personal information is adequate for the local demo. | Prompt 9 fixture review |
| A-002 | The approved knowledge set is small enough for in-memory deterministic filtering and ranking. | Prompt 14 retrieval evaluation |
| A-003 | A single process and SQLite support pilot concurrency and test volume. | End-to-end measurements; revisit before remote/multi-process use |
| A-004 | OrkaATS can eventually expose identity/context/permission and action capabilities through a controlled adapter. The Prompt 10 wire boundary exists, but OrkaATS owner/platform validation remains pending. | Before any live adapter deployment |
| A-005 | Request-scoped redacted candidate summaries are enough for mandatory guidance. | Prompt 11 context-flow review |
| A-006 | Local users can be represented by fixture identities selected through trusted server configuration. | Prompt 7 security review |
| A-007 | Version-controlled help/feature/page catalogs have named product owners and review. | Prompt 6 knowledge approval |
| A-008 | OrkaFin operational records can initially reside in one local SQLite database with process/file access limited to the operator. | Prompt 5 persistence review |
| A-009 | Recommendations can use meaningful events without collecting keystrokes or full candidate content. | Prompt 17 behavior evaluation |

## Unresolved questions and owners

`Open` means no implementation may hard-code an answer. A prompt may introduce a
clearly labeled provisional fixture only when its checkpoint requires review.

| ID | Question | Decision owner/checkpoint | Blocking effect |
|---|---|---|---|
| Q-001 | What are the authoritative OrkaATS stage IDs, display names, ordering, active status, and transition rules? | OrkaATS product owner; before knowledge/context approval | Blocks claiming stage guidance as authoritative; does not block Prompt 2 scaffold |
| Q-002 | Which candidate fields exist, which field names are themselves sensitive, and what may recruiter, limited viewer, admin, and other roles see? | Security + OrkaATS owner; Prompt 7 checkpoint | Blocks production-like redaction policy and Prompt 8 approval |
| Q-003 | How are record assignments/project/workspace visibility represented independently of role? | OrkaATS owner; Prompt 7 checkpoint | Blocks final record-access policy |
| Q-004 | In each Apps Script deployment mode, who executes the app, when is active-user identity available, and how is the assertion authenticated to OrkaFin? | Platform/security owner; before live adapter | Blocks live Apps Script integration and every production identity claim |
| Q-005 | What controlled HTTPS endpoint and server-to-server authentication/replay protocol will live Apps Script use? | Platform/security owner; before live adapter | Blocks live connectivity; local mock remains allowed |
| Q-006 | Will the optional action POC be included, and is `candidate.update_start_date` the selected low-risk action? | OrkaATS product + security; before Prompt 18 | Blocks Prompt 18/19 only; mandatory V1 may skip it |
| Q-007 | If Q-006 is approved, what are start-date format, timezone/partial-date rules, allowed states, validation, reversibility, and receipt semantics? | OrkaATS product/engineering; before Prompt 18 | Blocks action schema and execution |
| Q-008 | What are retention/deletion periods for conversations, events, feedback, proposals, receipts, and audits? | Product/privacy/security; before non-local deployment | V1 must minimize and document fixture cleanup; blocks production claim |
| Q-009 | Who owns and approves feature, page, help, and action catalog revisions, and how is staleness signaled? | Product owner; Prompt 6 checkpoint | Blocks declaring knowledge production-ready |
| Q-010 | Which meaningful events may be collected and which metadata fields are prohibited? | Product/privacy; before Prompt 17 | Blocks final event schema/policy |
| Q-011 | What exact development origins and ports are allowed by CORS? | Prompt 3 configuration review | Use configurable loopback defaults only; blocks broad browser exposure |
| Q-012 | What are local retention/reset expectations for mock adapter state and audit fixtures? | Engineering/security; Prompts 5 and 9 | Blocks reproducible fixture cleanup details |
| Q-013 | What are the first approved page IDs/features and ten production-quality questions? | OrkaATS product owner; Prompt 6 | Current scope questions are representative, not a content approval |
| Q-014 | Which exact service-authentication and end-user assertion protocol, issuer/audience rules, replay store, nonce lifetime, and key-rotation process will secure the hosted adapter? | Security + platform owner; before live adapter | Blocks adding auth configuration or using real candidate data |
| Q-015 | Which reviewed async HTTP client/transport owns TLS policy, connection limits, deployment observability, and secret injection for the hosted environment? | Platform owner; hosted deployment ADR | Blocks selecting a concrete live transport; mocked transport remains allowed |

## Decisions deliberately deferred

Provider vendor/model, cloud vendor/runtime, production database, distributed job
system, vector technology, cross-app event bus, and production observability are
not V1 selections. Naming one now would create false coupling. Their triggers and
invariants are in `docs/FUTURE_MIGRATION_PLAN.md`.

## Prompt 1 review record

| Field | Value |
|---|---|
| Reviewer | Pending |
| Review date | Pending |
| Outcome | Pending: approve, approve with recorded conditions, or request changes |
| Conditions/notes | Pending |

Until the outcome is recorded as approved, human review is the only issue that
blocks Prompt 2. Questions Q-001 through Q-013 are intentionally routed to later
checkpoints and must not be accidentally decided during scaffolding.

## Verification steps

- Confirm all D-001 through D-020 statements appear consistently in the scope,
  architecture, security model, threat model, and four ADRs.
- Search future code/migrations for direct Google Sheet clients and candidate
  persistence.
- At every checkpoint, update assumptions/questions with evidence and record any
  policy fixture as provisional or approved.
- Require an ADR status update and link validation whenever a decision is
  superseded.

## Change protocol and triggers

For a clarification that does not alter boundaries, update this file and affected
document in the same change. For a boundary change, add a new ADR with context,
alternatives, consequences, migration/rollback, verification, and reviewer. Mark
the old ADR superseded rather than rewriting history. Trigger this process for
candidate storage, direct Sheet access, live/remote identity, a new app/action,
vector retrieval, external-model authority, multi-service topology, or production
deployment.
