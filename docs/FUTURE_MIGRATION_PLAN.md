# Future Migration Plan

**Status:** Directional plan; no future platform is approved by Prompt 1

## Purpose

Local V1 must be useful without turning prototype shortcuts into permanent
architecture. This plan identifies stable seams, evidence-based change triggers,
and safe migration order. It is not a commitment to Cloud Run, a model vendor, a
vector database, or microservices.

## Invariants that survive every migration

1. Each Orka application owns its records, permissions, business rules, validation,
   and writes.
2. OrkaFin never directly reads or writes an application Sheet or operational
   store.
3. Candidate data is not copied into OrkaFin as a system-of-record table.
4. Browser identity, role, permissions, and action claims remain untrusted.
5. Application reads/writes use versioned typed adapter contracts and least
   privilege.
6. Retrieved/model text cannot override permissions, catalogs, confirmation, or
   receipts.
7. Deterministic provider and safe failures remain available for tests.
8. State change requires explicit user intent, execution-time authorization,
   owning-app validation, idempotency, audit, and a valid receipt.
9. Data collection remains minimized with explicit retention and ownership.

Changing an invariant requires a product/security architecture review, not a
routine implementation decision.

## Designed migration seams

| Local V1 component | Stable interface | Possible later implementation |
|---|---|---|
| Local fixture identity resolver | Typed `IdentityResolver` boundary | Authenticated Workspace/app assertion and centralized authorization inputs |
| Mock OrkaATS adapter | Versioned general Orka app adapter | Authenticated Apps Script HTTPS adapter or application service API |
| SQLite repositories | Domain repository/unit-of-work interfaces | Managed relational database after scale/reliability evidence |
| Version-controlled catalog loader | Versioned knowledge-source interface | Reviewed publishing service/object storage while preserving revisions |
| Deterministic retrieval | Retrieval result contract with provenance | Hybrid/semantic retrieval only after measured misses |
| Deterministic response provider | Provider-independent structured input/output | Optional external model with data handling and validation controls |
| In-process work | Explicit application services and events | Managed queue/tasks only for proven asynchronous workloads |
| Local logs/audits | Structured correlation/audit schemas | Central logging and protected audit store with retention/integrity controls |
| Static framework-free widget | Versioned API contract | Embedding in Apps Script or another Orka app without trusting the client |

Interfaces are not excuses to pre-build distributed abstractions. V1 implements
only what its current prompts require.

## Migration stages

### Stage 0 — Local deterministic pilot

Use one process, SQLite, synthetic fixtures, mock OrkaATS adapter, versioned files,
and deterministic responses. Validate grounding, permission redaction, failure
behavior, recommendations, and user usefulness. Keep the optional action mock-only.

**Exit evidence:** mandatory Prompt 20 security/regression suite passes; Prompt 21
demo is accepted; unresolved production identity/retention questions are listed,
not hidden.

### Stage 1 — Controlled live OrkaATS read integration

Before a live read, define an internet-reachable controlled HTTPS endpoint and an
authenticated versioned adapter protocol. Test actual Apps Script deployment
identity behavior. OrkaATS performs final record/field permission checks and
returns minimized summaries. Start read-only, with synthetic test workspace/data
where possible.

**Entry gates:** threat-model update; data-flow/privacy review; issuer/audience/
expiry/replay and key-rotation design; exact origins; TLS; timeouts; rate/size
limits; audit policy; incident rollback/kill switch.

**Rollback:** disable the live adapter by configuration and return to mock/read-only
mode without changing domain/application contracts.

Stage 1 must proceed in three separately reviewed increments:

1. Keep `AppsScriptOrkaATSAdapter` on mocked HTTP transport and synthetic payloads
   while both sides implement wire `v1` / adapter contract `1.0.0` fixtures.
2. If connectivity evidence is needed, use a short-lived controlled HTTPS tunnel
   with synthetic data only. Record topology, operator, expiry, exact allowlists,
   and teardown. A tunnel is not a hosting decision or production auth.
3. Enable read-only candidate traffic only on a reviewed hosted endpoint after
   service and end-user authentication, request integrity, replay prevention, key
   rotation, privacy, audit, monitoring, rollback, and Apps Script deployment-mode
   tests pass.

Apps Script server-side `localhost` never means a developer laptop. Browser access
to loopback remains a separate CORS/mixed-content-constrained untrusted-client
path; it cannot establish production identity.

### Stage 2 — Remote single-service pilot

Deploy the same modular service remotely only when more than one controlled user
or Apps Script server-side access requires it. Choose hosting and a managed
relational store through a fresh ADR. Add secret management, encryption, backups,
migrations, observability, SLOs, abuse controls, and data deletion/retention.

Cloud Run and Cloud SQL/Firestore are ecosystem-aligned candidates from the source
context, not decisions. A relational managed database is the natural first
evaluation because SQLAlchemy/Alembic and transactional action state already
exist; evidence may justify another choice.

**Rollback:** maintain version-compatible database migrations/backups and disable
live adapters/actions independently of guidance.

### Stage 3 — Additional Orka applications

Onboard one app at a time through adapter capability/version metadata and the same
contract test suite. The owning app maps generic identity/context/entity/action
contracts to its own policy. Do not add app-specific conditional logic to core
orchestration when an adapter or catalog owns the variation.

**Entry evidence:** OrkaATS pilot metrics show useful guidance, no unresolved
critical leakage, and a real use case for the next app. Define cross-app identity,
workspace, entity reference, consent, and audit semantics before cross-app reads.

### Stage 4 — Retrieval evolution

Retain deterministic metadata filtering as a mandatory first pass. Evaluate
semantic or vector retrieval only when a labelled query set shows material,
repeatable misses that catalog/schema/keyword improvements cannot solve.

Required ADR evidence includes corpus size/change rate, benchmark queries and
relevance metrics, permission-filter behavior, tenant isolation, provenance,
deletion/re-index behavior, latency/cost, embedding data handling, failure
fallback, and an operational owner. A vector database is not automatically needed;
an in-process or relational approach may be sufficient.

### Stage 5 — Asynchronous or multi-service extraction

Keep a modular monolith until measurements show that an operation needs independent
scaling, isolation, ownership, or long-running execution. Candidate examples are
knowledge ingestion or event-derived recommendation jobs, but neither justifies a
service today.

An extraction ADR must document load, latency/SLO, failure/retry/idempotency,
transaction boundaries, schema evolution, observability, deployment ownership,
cost, local developer impact, and rollback. Kafka, Pub/Sub, Redis, and Kubernetes
remain unselected until a demonstrated requirement matches them.

## Data migration rules

- Alembic owns OrkaFin relational schema history from the first persistent schema.
- Expand/contract migrations preserve a compatible application window for remote
  deployment; destructive cleanup follows verified backfill and rollback period.
- Export/import deals only in OrkaFin-owned records. Candidate data remains in the
  owning app and is re-resolved under current permissions.
- Every dataset has classification, owner, purpose, retention, deletion, backup,
  and restore expectations before remote storage.
- Confirmation plaintext and secrets are never migrated; token hashes expire under
  their original bindings.
- Audit migration preserves ordering, correlation, and integrity evidence while
  continuing to minimize sensitive values.

## Identity migration rules

Do not map browser email directly to production identity. A production design must
authenticate both the calling Orka application/service and the end user, bind the
workspace/deployment, validate freshness and replay, and define what happens when
the user identity cannot be obtained. Rollout begins deny-by-default and read-only.
Mock identity selection remains available only in an explicit non-production mode
that cannot coexist accidentally with live configuration.

## Prompt 10 adapter-shell handoff

The HTTP shell preserves `OrkaApplicationAdapter`; core and application services
do not know whether the injected implementation is mock or HTTP. Its current
configuration is intentionally small:

| Field | Default/bounds | Meaning |
|---|---|---|
| `enabled` | `false` | Construction fails safely while disabled. |
| `endpoint_url` | none | Required when enabled; absolute HTTPS only, with no credentials, query, or fragment. |
| `timeout_seconds` | `5.0`; greater than 0 and at most 10 | One transport deadline; the shell performs no retries. |
| `max_response_bytes` | `1,000,000`; 1,024–2,000,000 | Reject oversized responses before parsing. |

The transport is an injected `AsyncHttpTransport`; no concrete network client is
selected. Request bodies and responses use wire schema `v1`, adapter contract
`1.0.0`, exact general capability operation names, and canonical request-ID
propagation.

Known blockers before a real transport can carry candidate data are production
service authentication, user assertion verification, request signing or token
exchange, issuer/audience/expiry checks, replay/nonce storage, key rotation,
secret management, rate/abuse controls, deployment-mode identity evidence,
reconciliation, and operational review. There is deliberately no token or secret
configuration field yet; adding one without an approved protocol would fabricate
security.

Mock transport fixtures live in `tests/unit/test_apps_script_adapter.py` and cover
serialization, response parsing, version conflict, timeout, malformed response,
permission denial, invalid action receipt, disabled configuration, and secret-free
adapter logs. Prompt 11 should consume the unchanged general adapter interface and
continue using the mock adapter; it must not enable this shell or infer trusted
browser identity.

## Provider migration rules

Adding a model requires an explicit configuration flag, provider data-use/retention
review, timeout and budget controls, minimized/redacted structured input,
grounded-output validation, deterministic fallback, and comparative evaluation.
Conversation contents or candidate fields are not automatically approved for the
provider merely because they are visible to a user.

Provider removal or outage must not disable health checks, permissions, retrieval,
tests, or the deterministic demo. A provider can improve phrasing; it cannot
become the only implementation of product rules.

## Metrics that justify change

Collect only approved aggregate/meaningful signals. Relevant triggers include
measured request volume/concurrency, p95 latency, SQLite lock/availability issues,
knowledge corpus size and retrieval precision/recall, adapter failure rate,
grounding failure reports, permission-safety pass rate, recommendation acceptance,
action reconciliation failures, support burden, and recovery objectives.

No fixed user count or threshold is invented in Prompt 1. Owners set thresholds
before a migration experiment and compare against a baseline.

## Verification steps

For every migration:

1. Run the existing adapter/provider/repository contract suites against old and
   new implementations.
2. Run full security and leakage regression with synthetic markers.
3. Prove downgrade/disable/rollback procedures in a non-production environment.
4. Confirm no candidate table, direct Sheet client, browser authority, or
   provider-authority regression.
5. Update architecture, threat model, data inventory, runbook, and ADR status.
6. Obtain human approval at the checkpoint before exposing new trust boundaries.

## Change triggers

This plan itself must be revised when production requirements, regulation/data
classification, Orka application interfaces, availability goals, provider terms,
or measured pilot behavior invalidate an assumption. Technology availability by
itself is not a migration trigger.
