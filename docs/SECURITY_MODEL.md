# Local V1 Security Model

**Status:** Prompt 7 provisional local authorization policy; human review required before Prompt 8
**Security posture:** Local pilot with explicit mocks; not production authentication

## Security objectives

Local V1 must preserve four properties:

1. **Confidentiality:** a user sees only candidate records and fields that OrkaATS
   authorizes for that verified request.
2. **Integrity:** browser input, retrieved text, and model output cannot change
   identity, permissions, business rules, catalogued actions, or execution results.
3. **Accountability:** sensitive reads, denials, proposals, confirmations, and
   executions are correlated and auditable without copying sensitive content into
   logs.
4. **Honesty:** OrkaFin never fabricates a feature, source, permission decision,
   adapter result, or successful write.

Availability matters, but fail-closed confidentiality and integrity take priority
over returning a convenient answer.

## Authorities and trust levels

| Actor/component | Trust level | Authority |
|---|---|---|
| Browser/widget | Untrusted | May express a question, intent, and context hint only |
| Local fixture identity resolver | Test-only trusted simulator | Returns a configured synthetic identity; no production claim |
| OrkaFin API/application services | Trusted for orchestration and OrkaFin data | May validate, minimize, retrieve, respond, and audit; cannot grant candidate access |
| OrkaATS adapter boundary | Trusted only after configured transport/identity checks | Supplies request-scoped identity/context/permission/field facts and execution receipts |
| OrkaATS | Final application authority | Owns candidate permissions, validation, records, and writes |
| Approved knowledge catalogs | Controlled data | Ground factual guidance only; cannot establish identity or policy |
| Candidate text/notes | Sensitive untrusted data | No instructional authority; excluded from provider input by default |
| External model provider | Untrusted decision aid | May draft wording from minimized inputs; cannot authorize or attest success |
| OrkaFin SQLite | Trusted local persistence subject to access controls | Stores only OrkaFin-owned state; never candidate records |
| Operator/environment | Administrative trust | Supplies configuration/secrets and controls local file/process access |

Trust is not transitive. For example, approved help text remains content rather
than code, and an authenticated user still needs application, record, field, and
action authorization.

## Identity and authentication

The local demo selects from explicit synthetic identities on the trusted server
side. `IdentityResolutionRequest.trusted_subject_id` must be constructed from
server configuration or another trusted application mechanism; its trust label is
documentation, not authentication. Browser-submitted email, user ID, role,
permissions, workspace, and available actions remain only `ClientContextHint`
claims. `LocalFixtureIdentityResolver` ignores them, including when a browser
claims administrator privileges while the selected fixture is a limited viewer.

A local fixture identity is a test harness, not production authentication. It does not prove Google
Workspace identity resolution, Apps Script deployment behavior, request
authenticity, or protection against an attacker who can access the local service.
Unknown, unverified, or missing identity receives no candidate data. The synthetic
fixtures contain no passwords, tokens, real email addresses, or real people.

Before live Apps Script use, the team must define and test:

- who the Apps Script web app executes as and whether the active user is available;
- how OrkaFin authenticates the calling application and user assertion;
- issuer, audience, expiration, replay, key rotation, and workspace binding;
- behavior when Workspace identity is unavailable or hidden by deployment mode;
- account lifecycle and revocation.

## Authorization and redaction

Authorization is deny by default and evaluated by application services outside API
route handlers. Role is identity metadata and never creates a grant. The
`PermissionEvaluator` accepts a verified identity and a separate
`TrustedAuthorizationFacts` value produced by the owning adapter or explicit local
test harness. It uses those facts for:

- application access;
- current page access;
- record visibility or assignment;
- field visibility;
- action availability and explicit namespaced permission;
- action availability (which may already reflect current business-state
  eligibility) and a separate explicit permission.

Permissions use the existing catalog names; Prompt 7 adds no permission names.
Unknown names and catalog entries absent from the current trusted grant both deny.
Page, record, field, and available-action lists are explicit grants rather than
claims inferred from a role. A trusted adapter may narrow provisional local policy
at any scope, and OrkaFin cannot union, infer, or otherwise broaden that result.

`CandidateSummaryRedactor` first requires `candidate.view` and exact record
visibility. It then intersects each source field with that record's trusted field
allowlist and returns the established `CandidateSummary` with counts only. Hidden
field identifiers and values are not present in the output. Notes are excluded by
default, including for the administrator fixture. The redactor can include a
bounded excerpt only when both `candidate.notes.view` and the explicit
`notes_excerpt` field grant are present; it preserves the existing sensitive and
untrusted labels and never persists the excerpt. No Prompt 7 fixture grants this.
Activating notes in a real adapter still requires the previously documented review.

Authorization is re-evaluated when context is resolved and again immediately
before any optional state change. Cached permission decisions cannot outlive the
adapter response unless an approved TTL and revocation design exists.

The provisional fixture users, exact grants, field matrix, denial codes, and human
checkpoint are recorded in [`PERMISSION_MODEL.md`](PERMISSION_MODEL.md).

## Data minimization and storage

OrkaFin stores the minimum validated domain data necessary for its own operation.
Allowed categories include conversation metadata, bounded messages, source
references, meaningful event summaries, recommendations, feedback, action state,
hashed confirmation tokens, execution receipts, and audits.

The following are prohibited from OrkaFin persistence and routine logs:

- candidate rows or a `candidates` table;
- raw/full candidate notes or hidden candidate fields;
- unrestricted adapter responses or raw request bodies;
- passwords, API keys, OAuth tokens, session cookies, or confirmation plaintext;
- raw external-model prompts/responses where a minimized structured record is
  sufficient;
- Sheet identifiers or URLs unless specifically classified and required.

SQLite files, audit records, and mutable adapter fixture state are local sensitive
artifacts and must be excluded from version control. The reviewed synthetic
identity fixture configuration is version-controlled and contains no candidate
values or real personal information. Retention and deletion periods are open
questions that block a production claim.

## Retrieval and prompt-injection controls

Knowledge is loaded only from version-controlled schemas with stable IDs,
revisions, ownership, status, and permission metadata. Retrieval applies
deterministic app/page/version/permission filters before text matching. A document
cannot grant a permission, register an action, or override system behavior.

User questions, candidate text, help excerpts, past messages, and provider output
are all potentially adversarial data. The provider receives a bounded structured
input containing only permitted context and retrieved excerpts. Candidate notes
are absent by default. System rules and catalog/action definitions are supplied
through typed code-controlled inputs, not concatenated instructions from records.

Response validation checks response type, cited source IDs, allowed feature/action
IDs, and claims of execution. When grounding is absent or conflicting, return
unavailable/refusal rather than fill gaps from model memory.

## Optional action security

Actions are disabled in the mandatory path. If the optional proof of concept is
approved, exactly one typed, versioned action may be enabled. The controls are:

1. Catalog allowlisting and strict per-action input schema; no arbitrary tool name
   or dictionary executor.
2. Trusted identity, workspace, record visibility, explicit permission, adapter
   availability, current value, and business validation before proposal.
3. A safe preview of owning app, target ID, old/new permitted values, effects,
   warnings, and reversibility.
4. A cryptographically random, one-time, expiring confirmation secret stored only
   as a hash and bound to user, workspace, target, action/version, proposal, and
   parameter hash.
5. A separate explicit execution click followed by complete authorization and
   state revalidation.
6. An idempotency key and request ID propagated to the owning adapter.
7. Success only from a schema-valid adapter receipt. Timeout or ambiguous failure
   produces an unknown/reconciliation state, not fabricated certainty.
8. Append-oriented audit events for proposal, checks, preview, confirmation,
   tampering/replay, execution attempt, receipt, and final status.

Frontend code can display an action preview but cannot set confirmation state,
permission, execution result, or audit outcome.

## API, browser, and CORS controls

Local endpoints bind to a documented local interface. Request bodies and headers
have type, length, count, and version limits. Errors use safe codes and request
IDs, never tracebacks. State-changing requests require content-type validation and
anti-replay/confirmation controls; production CSRF design remains out of scope
until browser authentication is selected.

CORS uses an explicit development-origin allowlist. `*` is prohibited when
credentials or sensitive data are involved. Allowed origins, methods, and headers
are minimized. CORS is a browser control, not authentication; non-browser callers
can ignore it.

## Secrets, logs, and audit access

Secrets come from the server environment or a later secret store. `.env` values
are not committed, frontend JavaScript contains no secrets, and safe examples use
non-sensitive placeholders. Logging applies a central allowlist/redaction policy
to headers, query parameters, request bodies, adapter payloads, and exceptions.

Audit records are themselves sensitive because they reveal users, target IDs,
denials, and activity patterns. V1 exposes no general audit browsing endpoint.
Direct local database access is operator-only. A future audit UI requires its own
permission, field minimization, pagination, export controls, retention, and audit
of audit access.

## Safe failure rules

- Unknown/unverified identity: deny without candidate data.
- Forbidden field/record: omit the value; use a stable safe denial reason.
- Missing or stale knowledge: identify information as unavailable.
- Adapter unavailable/timeout: do not use client claims as fallback authority.
- Provider unavailable: use deterministic fallback if grounded input is intact.
- Malformed execution receipt: record failure/unknown; never claim success.
- Internal exception: correlate by request ID, return a safe envelope, and keep
  secrets/traceback out of the response.

## Verification matrix

| Control | Required verification |
|---|---|
| Identity boundary | Forged email/role/permission/action tests and missing-identity denial |
| Record/field access | Cross-user record tests and field-by-field redaction tests |
| Ownership | Migration/schema scan for candidate tables and adapter-only candidate fixture tests |
| Prompt injection | Adversarial user/help/note/history fixtures; no policy/action change |
| Grounding | Unknown feature/source rejection and cited revision checks |
| Provider independence | Full tests and demo with no external key/network |
| CORS | Allowed-origin and disallowed/wildcard-origin tests |
| Logging | Captured-log tests for tokens, notes, hidden fields, and tracebacks |
| Action safety | Tamper, expiry, replay, wrong-user, revoked-permission, timeout, invalid-receipt tests |
| Audit confidentiality | No public endpoint and redacted audit payload tests |

## Change triggers

Security review and an ADR are required before live Apps Script connectivity,
production identity, remote hosting, multi-user external access, an audit UI,
candidate-note processing, durable candidate caching, a new provider data policy,
new executable actions, or credentialed cross-origin browser access. No local test
result may be presented as evidence that those production risks are solved.
