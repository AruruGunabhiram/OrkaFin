# ADR-002: Orka Applications Retain Data and Write Authority

- **Status:** Proposed — pending Prompt 1 human approval
- **Date:** 2026-07-13
- **Decision owners:** OrkaFin and OrkaATS product/security owners
- **Scope:** Candidate data, permission, validation, and integration ownership

## Context

OrkaATS currently owns recruiting workflows and may store operational data in
Google Sheets through Apps Script. Directly reading that Sheet from OrkaFin would
bypass OrkaATS field/record permissions, couple OrkaFin to storage layout, duplicate
business rules, and create conflicting writers. Copying candidate rows into the
OrkaFin database would create a shadow candidate system of record with stale
permissions and deletion obligations.

Future Orka applications need a consistent integration shape, but their entities
and policies differ. The boundary must be general without becoming an unrestricted
generic storage or tool API.

## Decision

OrkaATS owns candidate data, record and field permissions, business rules,
validation, authoritative stages, and writes. OrkaFin must never read or write the
OrkaATS Google Sheet directly and must not persist a candidate table or durable
candidate-row replica.

All application data access uses a typed, asynchronous, versioned general Orka
application adapter contract. It exposes bounded capabilities such as resolving
identity/context, returning a permission-filtered selected-entity summary,
listing approved features/actions, and executing one explicitly approved action.
It does not expose unrestricted Sheet/database queries or a sole giant
`call(name, payload)` escape hatch.

For reads, OrkaATS verifies identity, workspace, record visibility, field
visibility, and relevant permissions and returns only allowed data. For writes,
OrkaFin supplies a catalogued versioned action, verified identity, exact confirmed
parameters, request ID, and idempotency key; OrkaATS revalidates and returns a typed
receipt or error.

## Persistence boundary

OrkaFin may own conversations, messages, approved source references, meaningful
events, recommendations, feedback, action proposal/confirmation/execution state,
adapter receipts, and audits. These records contain minimized references and safe
values only.

Candidate records, raw notes, private fields, attachments, authoritative current
state, and Sheet credentials/locations remain application-owned. An adapter-owned
mock may keep synthetic fixture state in memory, files, or a separate local store,
but its schema and lifecycle are not OrkaFin persistence. A request-scoped redacted
`CandidateSummary` is a view, not ownership.

## Trust and failure boundary

Browser-selected candidate IDs are hints that the adapter must verify. Browser
permission and identity fields are not accepted by the public context request at
all. Adapter data is trusted only through an authenticated/configured
implementation and for the relevant request; OrkaFin must re-resolve before a
write. An unavailable adapter cannot be replaced by browser values, provider
guesses, or stale local candidate copies.

Success requires a valid execution receipt matching owning app, action, target,
request, idempotency key, time, and outcome. A timeout or malformed receipt is
failed/unknown, never fabricated success.

## Consequences

Positive consequences:

- OrkaATS remains the single policy and write authority.
- Storage changes behind OrkaATS do not force OrkaFin business changes.
- Field-level least privilege is enforced before content reaches retrieval/model.
- Future apps can implement the same contract and retain their own rules.

Costs and limitations:

- The pilot depends on an adapter and cannot provide candidate guidance when it is
  unavailable.
- Contract/version coordination with each owning application is required.
- OrkaFin cannot perform arbitrary analytics over candidate rows.
- Mock conformance cannot prove real Apps Script identity, transport, or business
  behavior.

## Alternatives considered

**Direct Sheet access:** expedient but bypasses the application and creates storage
coupling/over-privilege. Rejected.

**Replicate all candidates into OrkaFin:** could simplify queries but creates stale
authorization, privacy/deletion, synchronization, and dual-authority problems.
Rejected.

**Make OrkaFin the centralized permission engine immediately:** may be evaluated
in the future, but OrkaATS is the current final authority and no shared policy
model is approved. Rejected for V1.

**Application-specific core services:** faster for the first screen but makes
future apps copy OrkaATS coupling. Use application-neutral contracts with
OrkaATS-specific adapter mapping instead.

## Verification

- Migration/schema tests fail if OrkaFin defines a `candidates` table or equivalent
  candidate-row store.
- Static/repository review finds no Google Sheets/Drive access in OrkaFin core;
  only an approved adapter transport may call an owning application endpoint.
- Adapter contract tests cover filtering, errors, capability versions, and receipt
  validity.
- Security tests prove modified client identity/record/permission/action claims do
  not broaden access.
- Failure tests prove adapter unavailability and malformed receipts cannot produce
  data or success.
- Fixture reset tests show mock candidate state is isolated from OrkaFin database.

## Change triggers

Any proposal for direct storage access, candidate caching/replication, centralized
permissions, cross-app entity joins, or a new write path requires a superseding ADR
and OrkaATS/security approval. It must document field classification, consent,
freshness/revocation, retention/deletion, encryption, reconciliation, audit,
incident response, and a migration/rollback plan.
