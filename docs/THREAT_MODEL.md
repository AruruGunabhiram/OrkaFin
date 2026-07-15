# Local V1 Threat Model

**Status:** Updated for Prompt 14; human security review required before Prompt 15
**Method:** Asset and trust-boundary review with abuse cases and testable controls

## Scope and assets

This model covers the local browser/widget, one OrkaFin process and SQLite store,
approved knowledge files, optional model boundary, and mock/versioned OrkaATS
adapter. It does not claim to model a production network, Google Workspace tenant,
or live Apps Script authentication.

Protected assets are permitted candidate fields, candidate existence and record
IDs, user/workspace identity, permission decisions, approved knowledge integrity,
conversation/event/feedback data, action intent and state, adapter receipts,
secrets, logs, and audit records.

Primary attackers are a user manipulating browser requests, a user entitled to one
record but not another, adversarial text stored in a question/document/candidate
field, a compromised or malfunctioning provider, and accidental operator or
developer exposure. Local machine compromise is residual risk outside application
controls.

## Boundary assumptions

- Browser values are attacker-controlled even when the UI normally hides them.
- The local fixture identity resolver and mock adapter are trusted test harnesses,
  not production security controls.
- OrkaATS remains the final authorization and write authority.
- Approved documents can contain malicious text and are not policy authorities.
- The OrkaFin database and logs may be read by the local operator; V1 has no
  multi-tenant database isolation claim.
- Actions are disabled unless the optional action checkpoint is explicitly passed.

## Security decisions for this threat model

The local service denies access when trusted identity, adapter policy, permitted
context, or grounding is unavailable. It never substitutes browser claims, stale
candidate copies, or model output for those missing authorities. Candidate data
remains OrkaATS-owned, candidate notes remain excluded from provider input by
default, and action execution remains disabled until the optional reviewed gates
exist. These are architecture decisions, not mitigations a feature may turn off.

## Threat register

### T-01 — Forged browser identity, role, permissions, or actions

**Attack:** A caller edits JSON, headers, hidden controls, or JavaScript to claim a
different email/workspace, administrator role, added permissions, record access,
or an available action.

**Impact:** Candidate leakage, privilege escalation, unauthorized proposal or
write, and misleading audits.

**Controls:** Use client values only as hints; resolve identity and authorization
through the trusted resolver/adapter; separate claimed and verified types; deny by
default; require namespaced permissions and record/field checks; bind optional
confirmation to verified identity/workspace; re-resolve before execution.

**Verification:** Send conflicting client and resolver identities; add unknown and
admin permissions; alter selected record/action; assert that responses match only
trusted policy and that denial audits use the verified identity/request ID.

**Residual risk/change trigger:** Fixture selection is not real authentication.
Any live or remote deployment requires an authenticated caller/user assertion and
deployment-mode tests.

### T-02 — Candidate record or field-level leakage

**Attack:** Enumerate IDs, modify selected entity, ask indirect summary questions,
use conversation history/recommendations/errors, or infer hidden data from
redaction metadata and timing.

**Impact:** Disclosure of candidate existence, notes, compensation/private fields,
or recruiting decisions.

**Controls:** Adapter-owned record visibility; allowlisted candidate summaries;
field redaction before retrieval/provider use; notes excluded by default; no raw
adapter persistence; bounded safe errors; conversation and recommendation inputs
carry only permitted fields; do not list sensitive hidden field names.

**Verification:** Cross-record and cross-role matrix tests, guessed/unknown IDs,
prior-message leakage tests, serialized response snapshots, database/log searches
for forbidden fixture markers, and equal safe response classes where enumeration
would matter.

**Residual risk/change trigger:** Exact field classification is unresolved and
must be reviewed after Prompt 7. Adding a field, cache, export, or audit browser
requires another leakage review.

### T-03 — Prompt injection in candidate notes, help documents, or history

**Attack:** Stored text instructs the assistant to ignore policy, reveal another
record, invent a feature, call an action, expose secrets, or mislabel success.

**Impact:** Data exposure, unsafe guidance, action abuse, or loss of trust.

**Controls:** Treat all content as data; exclude candidate notes from provider input
by default; keep permission/action definitions in code-controlled typed structures;
and separate system/developer templates from JSON-encoded trust-tagged data. Raw
help Markdown is search-only; only bounded summaries and human-verified structured
steps can become provider evidence. History minimization drops hidden roles and
sensitive entries and never treats retained history as evidence. Every grounded
output field requires a structured claim; server allowlists constrain response,
source, feature, and action IDs; category checks bind candidate facts to the adapter
summary source and steps to verified source steps. Providers cannot call adapters
or author action-success output. Unsafe provider output runs the same deterministic
validator/fallback and ultimately becomes unavailable.

**Verification:** Place injection strings in user questions, help fields, candidate
notes, and previous assistant messages. Assert no permission changes, no hidden
marker appears, no unlisted source/action is returned, and no action state exists.

**Residual risk/change trigger:** Claim mapping and lexical checks do not prove full
semantic entailment. A misleading paraphrase, malicious approved summary, poisoned
retrieval ranking, or server-misclassified history item may still affect output.
Finite fixtures do not cover novel attacks. Any candidate-note use, broader corpus,
client-labelled history, tool-calling provider, or autonomous planning requires a
new design and adversarial evaluation.

### T-04 — Action parameter or target tampering

**Attack:** After preview, alter candidate ID, field, new value, action version,
workspace, old value, or request payload; bypass the UI and call execution
directly.

**Impact:** A valid confirmation authorizes a different write.

**Controls:** Strict catalogued action schema; server-owned proposal; hash exact
canonical parameters; bind token to user/workspace/action version/target/hash;
separate proposal, confirmation, execution; re-read current state; adapter repeats
business validation; reject unknown fields and stale/conflicting state.

**Verification:** Mutate each bound element, reorder/canonicalize equivalent input,
add fields, swap users/workspaces/records, change state between steps, and call
execution without proposal/confirmation. No adapter execution should occur.

**Residual risk/change trigger:** The exact first action remains unapproved. Every
new action/input schema needs action-specific abuse cases and preview review.

### T-05 — Confirmation replay, theft, or expiry bypass

**Attack:** Reuse a confirmation, submit after TTL, steal it from logs/history,
race duplicate requests, or apply it to another session/user/workspace.

**Impact:** Duplicate or unauthorized writes and false user intent.

**Controls:** High-entropy one-time token; store hash only; short configured TTL;
atomic consume state; user/workspace/proposal/parameter binding; idempotency key;
separate explicit execution click; redact token and hash everywhere; audit replay
and expiry.

**Verification:** Expired, reused, concurrent, wrong-user/workspace, cancelled, and
logged-secret tests; database/log scans must not reveal plaintext; duplicate calls
must produce one adapter effect at most.

**Residual risk/change trigger:** Multi-process deployment requires database-level
atomicity and distributed idempotency review; local in-process assumptions cannot
carry forward.

### T-06 — Fabricated or ambiguous success

**Attack/failure:** A provider invents success, the adapter times out after a
possible write, a malformed receipt says success, or application code converts an
exception to friendly success text.

**Impact:** User acts on false state, duplicates changes, and audit records diverge
from OrkaATS.

**Controls:** Providers have no execution authority and Prompt 14 rejects both
structured `action_success` claims and narrowly recognized success prose. The
provider receipt allowlist is empty in V1; a model cannot turn a plausible receipt
ID into an attestation. A success domain object exists only in the separate action
path and requires a valid adapter receipt; validate owner/action/target/request/
idempotency/timestamp/outcome fields; use explicit failed versus unknown states;
never blindly retry ambiguous failures; reconcile through the owning adapter when
supported.

**Verification:** Provider success prose without receipt, timeout before/after mock
effect, malformed/mismatched receipt, adapter exception, duplicate retry, and
audit/response consistency tests.

**Residual risk/change trigger:** The secondary success-phrase recognizer is not a
semantic classifier and may miss novel wording; the primary protection is that no
provider claim category can report success. Real Apps Script must define idempotent
execution and receipt/reconciliation semantics before writes can be enabled.

### T-07 — Secrets or sensitive content in frontend code and logs

**Attack/failure:** Commit a key, embed it in widget JavaScript, log authorization
headers/confirmation tokens/raw prompts/notes, return a traceback, or record full
adapter payloads.

**Impact:** Credential compromise, candidate exposure, replay, and persistent leak
through source history or log aggregation.

**Controls:** Server-only environment configuration; safe `.env.example` names;
secret scanning in review/CI when tooling exists; central structured logging with
allowlists/redaction; bounded safe exception envelopes; no raw body/prompt logging;
synthetic fixtures; frontend bundle inspection.

**Verification:** Inject recognizable fake secret/note/token markers into all
error paths, capture logs and responses, inspect generated static assets, and scan
tracked files. Tests assert markers and tracebacks are absent.

**Residual risk/change trigger:** Adding a real provider, remote log service, or
client-side SDK requires data-flow and secret-management review plus rotation
procedures.

### T-08 — Audit log exposure or tampering

**Attack:** Read audits without authorization, infer candidate/user activity,
inject log fields/newlines, modify/delete an unfavorable record, or store hidden
data under metadata.

**Impact:** Privacy leakage and loss of accountability/non-repudiation.

**Controls:** No public audit browsing endpoint in V1; operator-only local file;
typed allowlisted audit schema; sanitized bounded text; append-oriented repository
operations for security events; correlation IDs; no raw notes/hidden values/token
hashes; audit sensitive denials and action transitions.

**Verification:** API route inventory, metadata validation tests, control-character
tests, update/delete repository restrictions, forbidden-marker database scans, and
expected audit sequence assertions.

**Residual risk/change trigger:** SQLite cannot provide production tamper evidence
or tenant isolation. Remote/multi-user deployment requires access control,
retention, encryption, immutable export or integrity mechanism, and audit-access
auditing.

### T-09 — Overly broad CORS and exposed local service

**Attack:** A malicious site calls a credentialed local endpoint, reads candidate
context, submits requests, or exploits wildcard/reflective origin behavior.

**Impact:** Cross-origin data leakage or action intent abuse.

**Controls:** Exact configurable development-origin allowlist; no wildcard with
sensitive responses/credentials; minimal methods and headers; no trust based on
Origin alone; bind locally by default; actions retain server-side confirmation and
identity controls.

**Verification:** Known origin succeeds; arbitrary, `null`, prefix/suffix lookalike,
and reflected origins fail; preflight exposes only required methods/headers; direct
non-browser calls still face authentication/authorization controls.

**Residual risk/change trigger:** Any HTTPS tunnel, LAN binding, hosted frontend,
or cookie authentication needs a new origin, CSRF, host-header, TLS, and abuse-rate
review.

### T-10 — Knowledge/catalog poisoning and stale guidance

**Attack/failure:** A malicious or accidental catalog edit invents a feature,
removes permission metadata, references an outdated workflow, or changes content
without traceable revision.

**Impact:** Incorrect guidance, permission-confusing recommendations, and unsafe
action proposals.

**Controls:** Version-controlled reviewed catalogs; strict schema and stable IDs;
status/owner/revision metadata; cross-reference validation; deterministic filtering;
actions defined in a separate explicit catalog; sources returned with responses;
raw help bodies excluded from provider evidence; only verified structured steps may
be emitted as steps; stale/missing content yields unavailable status.

**Verification:** Invalid permissions, missing owners/revisions, duplicate IDs,
broken references, disabled entries, injected instructions, and unknown actions
fail knowledge validation/retrieval tests.

**Residual risk/change trigger:** Schema validation cannot decide whether an
approved summary is truthful or malicious, and raw help text can still influence
retrieval ranking. External document ingestion or non-engineer publishing requires
signed/approved ingestion workflow, provenance, content review, rollback, and
freshness policy.

## Cross-cutting verification schedule

Threat cases become automated tests in the prompt that introduces the relevant
interface. Prompt 20 must run the complete adversarial suite regardless of whether
the optional action is implemented. A manual review must compare API schemas,
database migrations, logs, fixture markers, CORS settings, and widget bundles with
this register.

## Change triggers and process

Update this threat register whenever a trust boundary, protected data class,
identity method, adapter transport, retrieval source, provider, persistence
location, browser origin, or action changes. Record newly accepted residual risk
in `docs/DECISIONS.md` and create/supersede an ADR when the architecture boundary
changes. A passing local suite is not sufficient evidence for a production threat
model.

Before Prompt 15, the human reviewer must decide whether to accept the remaining
semantic-grounding, catalog-poisoning, history-classification, external-provider,
and red-team-coverage risks documented above. Until that review is recorded, the
assistant endpoint checkpoint is not passed.
