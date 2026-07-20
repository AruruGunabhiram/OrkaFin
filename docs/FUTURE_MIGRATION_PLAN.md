# Future Migration Plan

**Status:** Local V1 handoff. This is a gated direction, not a production deployment plan.

Local V1 is intentionally a single-process, loopback-only, synthetic-data system. Its stable seams are typed adapter capabilities, server-side trusted-session resolution, reviewed knowledge catalogs, bounded provider contracts, explicit action receipts, SQLite migrations, and minimized audits. Future work must preserve those seams rather than bypassing them with direct storage access.

## Mode 1: local mock mode (current)

- Synthetic fixtures are read only by `MockOrkaATSAdapter`; mutable mock action state stays in `var/mock_orka_ats_state.json`.
- OrkaFin uses local SQLite only for OrkaFin-owned records; no candidate table or replica exists.
- The deterministic provider is default; no network or provider key is needed.
- Fixture identity is server configuration, not authentication. Browser context is always untrusted.
- The one optional action is mock-only, confirmation-gated, receipt-backed, and resettable.

This mode is the baseline test/demo environment and remains available after later modes are added.

## Mode 2: controlled tunnel testing (not approved)

A temporary HTTPS tunnel may test a reviewed synthetic integration only after platform/security approval. It is not hosting, authentication, or a shortcut to real data.

Required gates:

- synthetic/test workspace only; no real candidate data or production credentials;
- fixed HTTPS endpoint allowlist, bounded request/response sizes, short expiry, and explicit teardown;
- service-to-service authentication, issuer/audience validation, nonce/replay rules, and key rotation design;
- exact Apps Script execution/identity behavior documented and independently verified;
- narrow CORS/CSRF/mixed-content review for any browser path; no browser-held service secret;
- observed request IDs, safe logs, alert/kill procedure, and a plan to disable the tunnel immediately; and
- contract tests plus manual test evidence that all permission and field checks remain app-owned.

Apps Script server code cannot assume it can reach a developer's `localhost`; a browser reaching loopback is a separate untrusted path.

## Mode 3: hosted API prerequisites (not approved)

Choose a hosted runtime only after the tunnel gate and a written architecture decision. Before exposing a service beyond loopback, define:

- network boundary, HTTPS/TLS termination, hostname/host-header policy, rate/abuse controls, request-size limits, and health/readiness behavior;
- production configuration separation, secrets injection/rotation, least-privilege service identity, and no client-side provider or adapter secret;
- managed database selection, migrations, backups, restore drills, encryption/access controls, concurrency/idempotency guarantees, and audit access controls;
- structured redacted observability: metrics, traces, request correlation, alerting, safe log retention, and operator access audit;
- deployment rollback/kill switch, compatibility/version rollout, data deletion/retention, incident response, and security review; and
- production CORS/CSRF/session rules based on the chosen browser topology.

Do not infer that a hosted API may read a Sheet or database. The adapter remains the only application-data boundary.

## Production identity and authorization

Before a live request, specify the end-user and service authentication protocol in detail: trusted issuer, audience, subject mapping, app/workspace binding, expiry, clock skew, nonce/replay persistence, revocation, deployment identity, key rotation, and failure behavior. The adapter resolves verified identity and permissions per request. It must recheck record/field/action permission at execution time.

Production identity is not a replacement for OrkaATS authorization. OrkaATS still owns record visibility, field policy, business validation, and writes.

## Secrets and provider policy

Use managed secret storage and rotation procedures, never `.env` on a shared host or browser JavaScript. Review a provider data policy before sending any minimized request externally: approved model/vendor, endpoint/TLS policy, retention/training terms, timeouts, response schema validation, outage fallback, cost/rate limits, and redaction verification. A provider never becomes a permission, feature, action, or success authority.

## Managed database migration

Migrate only OrkaFin-owned schemas through reviewed Alembic revisions. Establish access controls, encryption/backup/restore, migration rollback, tenancy strategy, retention/deletion, and append/tamper evidence for audits before non-local use. Candidate rows, raw notes, and a generic app-data cache remain out of scope unless a new ownership ADR approves them.

## Observability, retention, and incident response

Define what can be logged, who can query it, redaction tests, retention/deletion schedules, audit export/integrity, alert thresholds, incident owners, rotation/revocation, forensic access, and customer/user notification obligations. Local SQLite and process logs do not provide production tamper evidence, tenant isolation, or an incident program.

## Background processing only when justified

Do not introduce queues, workers, schedulers, Redis, Kafka, or a second service merely to mimic production. Add background processing only after a concrete workload needs durable asynchronous execution, an owner defines idempotency/retry/dead-letter/visibility/retention behavior, and a new ADR documents why synchronous bounded paths are insufficient. Background workers must use the same adapter, permission, audit, and data-minimization boundaries.

## What must remain inside OrkaATS

The following never move into OrkaFin merely to simplify integration:

- candidate records, notes, attachments, and system-of-record history;
- identity truth, role/workspace/record/field permission decisions;
- business rules, validation, concurrency, and final action execution;
- authoritative action receipt/reconciliation semantics; and
- OrkaATS-specific retention, legal, and operational ownership.

## Suggested V2 milestone

The recommended next milestone is **a reviewed synthetic OrkaATS adapter integration environment**, not a broad feature release. Deliver a concrete authenticated service-to-service protocol, a versioned test transport, contract/security tests against a synthetic isolated workspace, an approved field matrix/source catalog, receipt/reconciliation design for the one action, and an operator runbook. Only after that evidence should the project decide whether controlled tunnel testing is appropriate.
