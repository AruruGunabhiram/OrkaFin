# OrkaATS Apps Script Adapter Contract

**Status:** Prompt 10 transport boundary; not a completed live integration

**Wire schema:** `v1`

**General adapter contract:** `1.0.0`

**Owning application:** `orka_ats`

## Scope and authority

This contract maps the existing `OrkaApplicationAdapter` interface onto a future
OrkaATS Apps Script HTTPS boundary. OrkaATS remains authoritative for identity,
workspace membership, candidate visibility, field visibility, action availability,
business validation, and writes. OrkaFin consumes only typed, filtered responses.

The public contract contains application-level entity references, fields,
permissions, actions, and receipts. It contains no spreadsheet IDs, ranges, tab
names, cell coordinates, query handles, or direct storage operations. Any mapping
from OrkaATS application semantics to its operational store remains private to
OrkaATS.

`AppsScriptOrkaATSAdapter` is only a disabled-by-default HTTP client shell with an
injected transport. It has no production authentication implementation, no default
URL, no embedded secret, and no network client registration in the application
composition root. Its tests prove serialization and safe failure behavior against
mocked HTTP responses only.

## HTTP envelopes

Every request is one JSON object:

```json
{
  "schema_version": "v1",
  "adapter_contract_version": "1.0.0",
  "operation": "get_app_metadata",
  "request_id": "00000000-0000-4000-8000-000000000110",
  "app_id": "orka_ats",
  "payload": {
    "schema_version": "v1",
    "adapter_contract_version": "1.0.0",
    "request_id": "00000000-0000-4000-8000-000000000110",
    "app_id": "orka_ats"
  }
}
```

The payload is the exact typed general-contract request for `operation`. The outer
and inner versions, request ID, and app ID must agree. The HTTP client also sends
the request ID, wire version, and adapter contract version in headers for
correlation and early routing; headers do not replace envelope validation.

A successful response is:

```json
{
  "schema_version": "v1",
  "adapter_contract_version": "1.0.0",
  "operation": "get_app_metadata",
  "request_id": "00000000-0000-4000-8000-000000000110",
  "app_id": "orka_ats",
  "adapter_response_id": "apps-script-response-001",
  "responded_at": "2026-07-13T20:00:00Z",
  "outcome": "success",
  "payload": {
    "schema_version": "v1",
    "adapter_contract_version": "1.0.0",
    "request_id": "00000000-0000-4000-8000-000000000110",
    "app_id": "orka_ats",
    "adapter_response_id": "apps-script-response-001",
    "responded_at": "2026-07-13T20:00:00Z",
    "app_metadata": {
      "schema_version": "v1",
      "app_id": "orka_ats",
      "display_name": "OrkaATS",
      "description": "Permission-aware applicant tracking application.",
      "app_version": "1.0.0",
      "adapter_contract_version": "1.0.0",
      "status": "active"
    }
  }
}
```

`payload` must validate as the operation's exact response model. Envelope and
payload IDs and timestamps must match. Unknown fields, malformed JSON, wrong
operation, wrong bindings, and invalid nested receipts fail closed.

A failure response has the same outer correlation fields, `outcome="failure"`,
and a typed `AdapterFailure` in `failure`. The failure's version, request ID, app
ID, and response ID must match the outer envelope. Response bodies, endpoint URLs,
headers, identity assertions, and exception details must never be logged.

## Operation mapping

The HTTP operation name is exactly the existing capability value. Core services
continue to depend only on `OrkaApplicationAdapter`.

| HTTP `operation` | Typed request | Typed response | OrkaATS responsibility |
|---|---|---|---|
| `get_app_metadata` | `GetAppMetadataRequest` | `GetAppMetadataResponse` | Return bounded application metadata. |
| `resolve_current_user` | `ResolveCurrentUserRequest` | `ResolveCurrentUserResponse` | Resolve a user only from authenticated server-side evidence. |
| `resolve_context` | `ResolveContextRequest` | `ResolveContextResponse` | Verify page, workspace, and optional candidate selection. |
| `get_user_permissions` | `GetUserPermissionsRequest` | `GetUserPermissionsResponse` | Return current explicit authorization facts. |
| `get_page_metadata` | `GetPageMetadataRequest` | `GetPageMetadataResponse` | Return bounded metadata for the verified page. |
| `get_selected_entity_summary` | `GetSelectedEntitySummaryRequest` | `GetSelectedEntitySummaryResponse` | Return only visible candidate fields. |
| `get_available_features` | `GetAvailableFeaturesRequest` | `GetAvailableFeaturesResponse` | Return verified feature availability. |
| `get_available_actions` | `GetAvailableActionsRequest` | `GetAvailableActionsResponse` | Return action IDs available now; this grants no execution by itself. |
| `get_recent_user_events` | `GetRecentUserEventsRequest` | `GetRecentUserEventsResponse` | Return bounded, privacy-minimized meaningful events. |
| `search_allowed_records` | `SearchAllowedRecordsRequest` | `SearchAllowedRecordsResponse` | Search only records and fields already visible to the user. |
| `execute_approved_action` | `ExecuteApprovedActionRequest` | `ExecuteApprovedActionResponse` | Revalidate and execute one fully bound action. |
| `log_feedback` | `LogFeedbackRequest` | `LogFeedbackResponse` | Accept a non-authoritative, replay-protected feedback signal. |

The remote deployment advertises only capabilities it implements. Unadvertised
operations return `unsupported_capability`; they do not return empty success.

## Trusted identity assertions

Browser-provided identity, email, role, permissions, workspace, selected record,
and available actions are untrusted hints. An Apps Script page running in a user's
browser does not become an identity authority merely because it is served by
OrkaATS.

Before `ResolveCurrentUserResponse` may use `adapter_verified`, the production
design must let OrkaFin verify all of the following from authenticated evidence:

- the OrkaATS deployment/service issuer and intended OrkaFin audience;
- the calling deployment and owning application;
- a stable subject, and how the Apps Script execution mode obtained it;
- issuance, expiry, nonce, and request/deployment binding;
- integrity/authenticity through an approved signing or token-exchange protocol;
- replay status and key/token rotation state; and
- current workspace membership and account status from OrkaATS authority.

Apps Script active-user behavior varies with deployment and execution identity.
It must be tested in the chosen deployment; an absent user identity denies rather
than falling back to browser email. The current shell verifies none of these
production properties and therefore is not approved for real candidate data.

## Permission behavior

Permissions are evaluated and filtered inside OrkaATS before a response is built:

- app and page access are explicit and omission denies;
- role labels do not imply a record, field, or action grant;
- record visibility is independently checked for the verified user and workspace;
- field values are returned only when that exact field is visible; hidden values
  and hidden field names are absent;
- search operates only over already-allowed records and fields;
- an action ID indicates availability only, not permission to execute; and
- execution revalidates identity, record, field/action permission, action version,
  current state, exact parameters, idempotency, and business rules.

Missing, private, out-of-workspace, and inaccessible records may deliberately use
the same safe failure to avoid existence disclosure. OrkaFin never widens a grant
and never uses browser claims, cached candidate data, or model output as fallback
authority.

## Errors and retries

| Adapter code | Typical HTTP status | Retry rule |
|---|---:|---|
| `unauthorized` | 401 | Do not retry without new authenticated evidence. |
| `forbidden` | 403 | Do not retry unchanged. |
| `not_found` | 404 | Do not retry unchanged. |
| `validation_failed` | 400/422 | Correct the typed request; do not retry unchanged. |
| `conflict` | 409 | Re-resolve authoritative context/state before a new attempt. |
| `timeout` | 408/504 | Read calls may be retried only under a bounded caller policy. Writes require idempotency lookup/reconciliation first. |
| `unavailable` | 429/502/503 | Apply bounded backoff only where the operation is safe to retry. |
| `internal_failure` | 500/other invalid response | Fail closed; investigate by safe correlation IDs. |
| `unsupported_capability` | 400/501 | Do not retry; negotiate/deploy a supported contract. |

A valid typed failure takes precedence over coarse HTTP mapping. Malformed 2xx
responses become `internal_failure`. Transport timeout becomes `timeout`; it is
not success. The shell performs no automatic retries, especially for actions.

## Request IDs, idempotency, and action receipts

The same canonical UUID request ID is propagated in the HTTP header, outer
envelope, typed payload, response, failure, receipt, OrkaFin audit, and safe logs.
OrkaATS creates a unique `adapter_response_id` for each authoritative response.

`execute_approved_action` and `log_feedback` also propagate the typed idempotency
key in their payload. OrkaATS stores/checks action idempotency under its own
authority and returns the prior authoritative outcome for a valid replay. It must
not execute twice because the HTTP client retried.

Action success exists only when `ExecuteApprovedActionResponse.receipt` is valid
and matches the request's app, action ID/version, target, request ID, idempotency
key, and configured adapter identity. The receipt includes an OrkaATS-owned
transaction/reference ID, explicit outcome, and UTC execution/receipt times. A
failed receipt includes a safe failure code. A timeout after dispatch is ambiguous
until reconciled; OrkaFin must not state either success or “no change” without an
authoritative receipt.

## Limits and compatibility

The client configuration defaults to a 5-second deadline, rejects values above
10 seconds, and accepts at most 1,000,000 response bytes (configurable only from
1,024 through 2,000,000 bytes). Typed domain models separately bound lists and
text. A production review may choose tighter per-operation deadlines; increasing
these hard limits requires explicit resource/abuse review.

Wire schema, adapter contract, adapter implementation, and individual capability
versions evolve independently. Requests declare `v1` and `1.0.0`; the receiver
must reject an unsupported version explicitly and must never silently coerce or
downgrade. Additive capability support is advertised in adapter metadata. A
breaking payload or semantic change requires a new compatible deployment path and
contract tests covering both sides during migration.

## Apps Script `doPost` routing pseudocode

This is routing pseudocode, not production Apps Script code. It deliberately omits
storage access, authentication implementation, and application business logic.

```javascript
function doPost(event) {
  const authenticatedCaller = authenticateAndVerifyReplay(event); // REQUIRED, TBD
  const envelope = parseBoundedJson(event.postData.contents);
  requireSupportedVersions(envelope.schema_version,
                           envelope.adapter_contract_version);
  requireRequestBindings(envelope, authenticatedCaller);

  const routes = {
    get_app_metadata: handleGetAppMetadata,
    resolve_current_user: handleResolveCurrentUser,
    resolve_context: handleResolveContext,
    get_user_permissions: handleGetUserPermissions,
    get_page_metadata: handleGetPageMetadata,
    get_selected_entity_summary: handleSelectedEntitySummary,
    get_available_features: handleAvailableFeatures,
    get_available_actions: handleAvailableActions,
    get_recent_user_events: handleRecentEvents,
    search_allowed_records: handleAllowedSearch,
    execute_approved_action: handleApprovedAction,
    log_feedback: handleFeedback
  };

  const handler = routes[envelope.operation];
  if (!handler) return typedFailure("unsupported_capability", envelope);

  try {
    const typedRequest = validateOperationPayload(envelope.operation, envelope.payload);
    const filteredResult = handler(typedRequest, authenticatedCaller);
    return typedSuccess(envelope, filteredResult);
  } catch (safeError) {
    return mapToTypedFailure(safeError, envelope);
  }
}
```

## Four local integration modes

| Mode | Connectivity | Trust/data rule | Status |
|---|---|---|---|
| Mock adapter | OrkaFin calls `MockOrkaATSAdapter` in process. | Synthetic fixtures and fixture identity only. | Default and fully testable offline. |
| Browser-local demo | A controlled browser page calls loopback OrkaFin directly. | CORS uses exact loopback origins; mixed-content rules may block an HTTPS page calling HTTP localhost; every browser identity/context claim remains untrusted. Use the mock authority. | Development convenience, not Apps Script server integration. |
| Controlled HTTPS tunnel | A temporary tunnel exposes a narrowly bound local endpoint, or exercises the Apps Script endpoint path, for explicit connectivity testing. | Short-lived URL, synthetic data, exact allowlists, operator supervision, no production identity claim, revoke immediately after test. | Temporary test technique, never production architecture. |
| Later hosted API | OrkaFin runs at a reviewed HTTPS deployment reachable by the intended browser/server path. | Requires real service/user authentication, signing or token exchange, replay prevention, key rotation, secret management, audit, rate limits, monitoring, and deployment review. | Future architecture decision; not implemented. |

Apps Script server-side code runs on Google infrastructure. Its `localhost` is not
the developer laptop, so `UrlFetchApp` cannot be assumed to reach a developer's
loopback FastAPI process. A browser on the developer machine may reach loopback,
but that is a distinct untrusted-client path subject to CORS and browser
mixed-content policy.

## Gates before any live candidate data

All of these are mandatory before replacing synthetic data:

1. Security and platform approval of the exact topology and Apps Script deployment
   identity behavior.
2. Mutual service authentication or equivalent approved request signing/token
   exchange, with issuer/audience/expiry verification and key rotation.
3. Replay protection bound to request ID, nonce, deployment, operation, and expiry;
   durable idempotency/reconciliation for writes.
4. TLS-only endpoints, secret management, endpoint allowlisting, bounded request
   and response sizes, rate limits, abuse controls, and safe timeouts.
5. OrkaATS-owned record/field/action authorization tests using synthetic or
   isolated test workspaces before real data.
6. Exact CORS and content-security policy for any browser path; no wildcard origin
   and no browser-held server credential.
7. Redacted structured logging, protected audit trail, retention/deletion policy,
   incident response, kill switch, rollback to mock/read-only mode, and monitoring.
8. Privacy/data-flow and deployment review confirming no direct operational-store
   access or durable candidate replica in OrkaFin.

Until those gates pass, the safe handoff is the mock adapter plus the mocked HTTP
fixtures in `tests/unit/test_apps_script_adapter.py`. Passing these tests does not
mean live Apps Script integration, authentication, or candidate traffic works.
