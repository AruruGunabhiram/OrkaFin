# Local V1 API

## Trusted context resolution

`POST /api/v1/contexts:resolve` converts browser hints into request-scoped facts
verified by the configured owning-application adapter. The `:resolve` action name
is intentional: the call performs verification and returns an ephemeral value; it
does not create or update a durable `context` resource. The `/api/v1` prefix fixes
the public contract version independently of internal package versions.

The request body is exactly `ClientContextHint`: required `app_id` and `page`
navigation hints plus an optional `{type, id}` selection. The inherited
`schema_version` may be omitted and defaults to `v1`. There is no public workspace
hint or client request-ID field because the trusted session resolves workspace and
request middleware owns the request ID. No header or body field selects a trusted
user. The application composition root supplies a `TrustedSessionResolver` from
server/session state. The default resolver returns no subject and therefore fails
closed. `StaticTrustedSessionResolver` is a synthetic test harness only.

Example request:

```json
{
  "app_id": "orka_ats",
  "page": "candidate_profile",
  "selected_entity": {
    "type": "candidate",
    "id": "CAND-1042"
  }
}
```

`extra="forbid"` applies at both request levels. Identity, email, role,
permission, available-action, workspace, request-ID, legacy `*_hint`, and any
other undeclared fields receive `422 validation_error`; none reaches identity or
authorization resolution. With the trusted synthetic session fixed to
`limited_viewer`, the important portion of the response is:

```json
{
  "schema_version": "v1",
  "trust_label": "verified_for_response_lifetime",
  "verification_source": "application_adapter",
  "adapter_response_id": "mock-resolve_context-00000811",
  "component_trust": {
    "schema_version": "v1",
    "app": {
      "schema_version": "v1",
      "trust_label": "trusted_for_response_lifetime",
      "verification_source": "application_adapter",
      "source_response_id": "mock-resolve_context-00000811"
    },
    "identity": {
      "schema_version": "v1",
      "trust_label": "trusted_for_response_lifetime",
      "verification_source": "application_adapter",
      "source_response_id": "mock-resolve_current_user-00000811"
    },
    "page": {
      "schema_version": "v1",
      "trust_label": "trusted_for_response_lifetime",
      "verification_source": "application_adapter",
      "source_response_id": "mock-get_page_metadata-00000811"
    },
    "workspace": {
      "schema_version": "v1",
      "trust_label": "trusted_for_response_lifetime",
      "verification_source": "application_adapter",
      "source_response_id": "mock-resolve_context-00000811"
    },
    "selected_entity": {
      "schema_version": "v1",
      "trust_label": "trusted_for_response_lifetime",
      "verification_source": "application_adapter",
      "source_response_id": "mock-resolve_context-00000811"
    },
    "permissions": {
      "schema_version": "v1",
      "trust_label": "trusted_for_response_lifetime",
      "verification_source": "application_adapter",
      "source_response_id": "mock-get_user_permissions-00000811"
    },
    "available_actions": {
      "schema_version": "v1",
      "trust_label": "trusted_for_response_lifetime",
      "verification_source": "application_adapter",
      "source_response_id": "mock-get_available_actions-00000811"
    },
    "candidate_summary": {
      "schema_version": "v1",
      "trust_label": "trusted_for_response_lifetime",
      "verification_source": "application_adapter",
      "source_response_id": "mock-get_selected_entity_summary-00000811"
    }
  },
  "request_id": "00000000-0000-4000-8000-000000000811",
  "page_id": "candidate_profile",
  "identity": {
    "schema_version": "v1",
    "user_id": "mock-user-limited-viewer",
    "display_name": "Synthetic Limited Viewer",
    "role": {
      "schema_version": "v1",
      "role_id": "limited_viewer",
      "display_name": "Limited viewer",
      "owner_app_id": "orka_ats"
    },
    "verification_status": "adapter_verified",
    "verified_at": "2026-07-13T20:00:00Z",
    "verification_reference": "mock-orka-ats:limited_viewer"
  },
  "selected_entity": {
    "schema_version": "v1",
    "app_id": "orka_ats",
    "entity_type": "candidate",
    "entity_id": "CAND-1042"
  },
  "permissions": ["candidate.view"],
  "available_action_ids": [],
  "candidate_summary": {
    "schema_version": "v1",
    "candidate_id": "CAND-1042",
    "visible_fields": [
      {"field_id": "display_name", "visibility": "visible"},
      {"field_id": "recruiter", "visibility": "visible"},
      {"field_id": "recruitment_stage", "visibility": "visible"}
    ],
    "visibility": {
      "schema_version": "v1",
      "visible_field_count": 3,
      "redacted_field_count": 5,
      "redaction_applied": true,
      "explanation_code": "field_permissions_applied"
    },
    "source_adapter_response_id": "mock-get_selected_entity_summary-00000811",
    "valid_for_request_id": "00000000-0000-4000-8000-000000000811",
    "retrieved_at": "2026-07-13T20:00:00Z"
  }
}
```

The adapter-verified email remains in the internal request-scoped `UserIdentity`
used by authorization and audit construction. Public `ResolvedPageContext`
contains the minimized `ResolvedUserIdentity`, whose schema has no email field.

The abbreviated visible-field objects above omit their allowed values only to
keep this review example compact; the real typed response contains the complete
allowed `label`, `sensitivity`, and value objects. It never contains hidden field
IDs/values or raw candidate notes. If no candidate is selected or the referenced
candidate is missing, `selected_entity`, `candidate_summary`, and their trust
entries are `null`; OrkaFin does not invent an entity.

## Safe failures

All failures use the versioned `ApiError` envelope and the middleware request ID.

| HTTP | Code | Meaning and disclosure rule |
|---:|---|---|
| 401 | `identity_unverified` | No trusted adapter identity; no candidate data is returned |
| 404 | `app_not_supported` | Requested app has no configured V1 adapter; no application data is returned |
| 404 | `page_not_supported` | Requested page is unknown to the configured app; no application data is returned |
| 403 | `context_access_denied` | Trusted app/page facts deny access; no claimed grant is echoed |
| 403 | `candidate_access_denied` | Exact candidate/permission check failed; candidate existence and fields are not disclosed |
| 422 | `validation_error` | Request shape failed bounded validation; only field locations are returned |
| 503 | `adapter_unavailable` | Configured adapter is unavailable, times out, or otherwise cannot return trusted application data |
| 500 | `internal_error` | Unexpected safe failure; no exception content or candidate data |

The endpoint performs no answer generation, recommendation, action proposal,
confirmation, or write.

Example rejected role/permission claim:

```json
{
  "schema_version": "v1",
  "code": "validation_error",
  "message": "Request validation failed.",
  "request_id": "00000000-0000-4000-8000-000000000811",
  "details": {"fields": ["body.role", "body.permissions"]}
}
```

Example private-candidate denial:

```json
{
  "schema_version": "v1",
  "code": "candidate_access_denied",
  "message": "The requested candidate information is not available for the verified account.",
  "request_id": "00000000-0000-4000-8000-000000000811"
}
```

## Audit behavior

- A permitted candidate summary creates `candidate_read` / `allowed` before the
  API returns it. Details contain only visible/redacted counts, a boolean, and the
  adapter source label.
- A denied app, page, or record decision creates `permission_denied` / `denied`
  before the safe error. Details contain only the check type and stable decision
  code.
- Missing/unverified identity creates `identity_denied` / `denied` with no actor
  or target.
- The audit target may contain the bounded candidate reference needed for review.
  Audit details and logs contain no browser claims, hidden fields, field values,
  raw candidate notes, or unrestricted adapter payloads.

There is no public audit-read endpoint.

The minimized internal audit details for the examples above are:

```json
{
  "event_type": "candidate_read",
  "outcome": "allowed",
  "target_entity_id": "CAND-1042",
  "details": {
    "visible_field_count": 3,
    "redacted_field_count": 5,
    "redaction_applied": true,
    "source": "application_adapter"
  }
}
```

```json
{
  "event_type": "permission_denied",
  "outcome": "denied",
  "target_entity_id": "CAND-1099",
  "details": {
    "check": "record",
    "decision_code": "record_access_denied"
  }
}
```

## Assistant and conversation API

The local demo base URL is `http://127.0.0.1:8000`. Browser clients may use
the explicit loopback origins configured by `ORKAFIN_ALLOWED_ORIGINS` (the
defaults are `http://127.0.0.1:8000` and `http://localhost:8000`). Requests may
send a canonical UUID in `X-Request-ID`; the service otherwise generates one and
always returns it in the response header and response envelope.

All browser-supplied context is a hint. There is no user, email, role,
permission, workspace, or action field in any assistant request. The server-side
trusted session resolver and owning-application adapter establish those facts for
each call.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Local process health. |
| `GET` | `/api/v1/apps/{app_id}/metadata` | Adapter-owned public app metadata. |
| `GET` | `/api/v1/apps/{app_id}/features` | Controlled product catalog; not a per-user availability grant. |
| `POST` | `/api/v1/contexts:resolve` | Resolve a browser hint into ephemeral trusted context. |
| `POST` | `/api/v1/action-proposals` | Prepare the one catalogued mock action and issue an expiring confirmation challenge. |
| `POST` | `/api/v1/action-proposals/{proposal_id}/confirmations` | Accept or reject intent; acceptance still performs no write. |
| `POST` | `/api/v1/action-proposals/{proposal_id}:execute` | Revalidate and execute the confirmed action once through the mock adapter. |
| `POST` | `/api/v1/assistant/queries` | Execute one grounded assistant turn. |
| `POST` | `/api/v1/events` | Record one allowlisted, permission-bound meaningful product event. |
| `POST` | `/api/v1/recommendations:evaluate` | Evaluate deterministic source-backed recommendation rules. |
| `POST` | `/api/v1/feedback` | Record feedback for an owned recommendation and optional preference. |
| `GET` | `/api/v1/conversations/{conversation_id}?app_id={app_id}&page={page}` | Read a conversation after revalidating its verified owner and workspace. |

There is deliberately no audit-read endpoint.

### Action proposal, confirmation, and execution endpoints

`POST /api/v1/action-proposals` accepts only
`candidate.update_start_date`, exact parameters
`{"start_date":"YYYY-MM-DD"}`, and `ClientContextHint`. Identity, workspace,
permission, action availability, current value, request ID, parameter hash, and
idempotency key are resolved or generated by the server. A successful `201`
response contains the exact owning app, candidate target, affected user/workspace,
old/new permitted values, reversibility, warnings, proposal/challenge expiry, and
one plaintext confirmation challenge. It omits the parameter hash and persisted
challenge hash.

`POST /api/v1/action-proposals/{proposal_id}/confirmations` accepts `accept` or
`reject`, the same exact parameter value, the challenge, and a fresh context hint.
Accept re-resolves and compares the trusted user, workspace, target, permission,
action availability, catalog version, and current preview value. It returns
`proposal_status=confirmed`, `confirmation_status=accepted`,
`execution_ready=true`, `execution_enabled=true`, and `execution_state=ready`.
Reject produces cancelled/rejected state. Neither branch calls the execution
adapter or creates an execution row.

`POST /api/v1/action-proposals/{proposal_id}:execute` accepts only a fresh
`ClientContextHint`. It re-resolves identity/context and rechecks candidate
visibility, permission, available action, current state, action version, and
parameter hash. It consumes the accepted confirmation, reserves the proposal's
server-generated idempotency key, calls `execute_approved_action` once, and
returns `ActionExecutionResponse` with a persisted `ActionExecutionResult`.

`succeeded` requires a valid matching `AdapterExecutionReceipt`. Explicit adapter
rejection returns `failed` with `OrkaATS could not complete the request. No changes
were made.` Timeout, unavailable transport, unexpected failure, or an invalid
receipt returns `unknown` and reconciliation-safe wording that does not assert no
change. A repeated endpoint request returns the stored result with
`idempotent_replay=true` and makes no adapter call.

Action-specific safe failures are:

| HTTP | Code | Meaning |
|---:|---|---|
| 403 | `action_access_denied` | Current trusted permission/action/record facts do not allow preparation, acceptance, or execution |
| 403 | `action_confirmation_invalid` | Token, parameters, user, workspace, or target binding did not verify; mismatch is not disclosed |
| 404 | `action_not_available` | Action is not the exact active catalogued mock action |
| 404 | `action_proposal_not_found` | Proposal/challenge pair is unavailable |
| 409 | `action_state_conflict` | Proposal is terminal, replayed, raced, or has a stale preview/catalog version |
| 410 | `action_confirmation_expired` | Shared proposal/challenge TTL elapsed |
| 422 | `action_input_invalid` | Validly shaped value is an invalid no-op for the current safe value |

Malformed dates/extra fields use the standard `422 validation_error`; adapter
outage remains `503 adapter_unavailable`. Pre-adapter denials safely state that no
change was made. An execution timeout or ambiguous response never makes that
assertion. Errors and results return no hidden candidate values, confirmation
secrets, or hashes. See
[`ACTION_AND_CONFIRMATION_FLOW.md`](ACTION_AND_CONFIRMATION_FLOW.md) for complete
examples, binding, TTL, execution receipts, idempotency, and audits.

### `POST /api/v1/assistant/queries`

Request fields are bounded: `question` is a trimmed 1–500 character string;
`context` is a `ClientContextHint`; and `conversation_id` is optional. Omit the
conversation ID to create an OrkaFin-owned conversation. A supplied ID is never
trusted: it is checked against the verified user and workspace before loading its
history. Hidden prompts, provider payloads, secrets, and candidate values are
never persisted.

```json
{
  "question": "Explain this page.",
  "context": {
    "app_id": "orka_ats",
    "page": "candidate_profile"
  }
}
```

Grounded success includes the response, request, conversation, grounding, and
approved source references. Source records are returned only when the response
cites them.

```json
{
  "schema_version": "v1",
  "response_id": "response:…",
  "conversation_id": "conversation:…",
  "request_id": "00000000-0000-4000-8000-000000000815",
  "grounding_status": "grounded",
  "content": {
    "kind": "grounded_guidance",
    "text": "Candidate profile: Present a permission-filtered provisional view of one candidate.",
    "steps": [],
    "source_ids": ["candidate_profile"]
  },
  "sources": [{"source_id": "candidate_profile", "source_type": "page_catalog"}],
  "created_at": "2026-07-13T20:00:00Z"
}
```

The supported V1 questions are page explanations, feature questions,
what-can-I-do-here guidance, candidate-summary questions, and step-by-step or
next-step guidance when verified instructions exist. Catalog content currently
marked provisional never becomes verified steps merely because it is retrieved;
the response is honestly unavailable when verified steps are absent.

Candidate summaries are requested only for recognized candidate-summary queries
with a selected candidate. The adapter returns only permitted fields. Standard
visible fields may appear in the immediate response; the persisted assistant
message is a non-sensitive acknowledgement rather than a copy of candidate data.

```json
{
  "question": "Give me the candidate summary.",
  "context": {
    "app_id": "orka_ats",
    "page": "candidate_profile",
    "selected_entity": {"type": "candidate", "id": "CAND-1042"}
  }
}
```

An unknown feature is a successful transport call with an explicit unavailable
answer, not a fabricated capability:

```json
{
  "grounding_status": "unavailable",
  "content": {
    "kind": "unavailable_information",
    "text": "Approved information is not available for this request.",
    "reason_code": "source_missing"
  },
  "sources": []
}
```

### Events, recommendations, and feedback

`POST /api/v1/events` accepts only `app_opened`, `page_viewed`, or
`candidate_selected` with a `ClientContextHint` and bounded metadata. The server
resolves identity/context and writes a minimized OrkaFin event; callers cannot
supply actor, workspace, permission, or arbitrary event types.

`POST /api/v1/recommendations:evaluate` accepts only the context hint. It records
a bounded page interaction, evaluates reviewed catalog rules against verified
permissions/features/recent events, and returns source references. It does not
open the widget, make an action available, or infer permission from a catalog.

```json
{
  "context": {"app_id": "orka_ats", "page": "recruitment_pipeline"}
}
```

The synthetic Local V1 rule can return:

```json
{
  "preference": "enabled",
  "recommendations": [{
    "rule_id": "review_recruitment_pipeline",
    "title": "Review the recruitment pipeline",
    "feature_id": "candidate_stage_tracking",
    "source_references": [
      "catalog://orka_ats/recommendations/review_recruitment_pipeline",
      "catalog://orka_ats/features/candidate_stage_tracking"
    ]
  }],
  "suppressed_rule_ids": []
}
```

`POST /api/v1/feedback` accepts a recommendation ID returned for the same verified
user/workspace, one of `helpful`, `not_helpful`, `accepted`, or `dismissed`, a
fresh context hint, an optional bounded comment, and optional preference
`enabled`, `reduced`, or `disabled`. Recommendation ownership is rechecked.
Accepted rules do not repeat when recurrence is disabled; a dismissed rule is
suppressed for its configured interval. Free text is content-redacted before
persistence.

```json
{
  "recommendation_id": "recommendation:synthetic-example",
  "feedback_type": "helpful",
  "context": {"app_id": "orka_ats", "page": "recruitment_pipeline"}
}
```

There is no public endpoint for events, audit history, candidate export, or raw
adapter payloads. A local operator can inspect bounded redacted event/audit rows
with `python scripts/inspect_local_activity.py`; see
[`LOCAL_SETUP.md`](LOCAL_SETUP.md#inspect-local-events-and-audits).

### Conversation and application responses

`GET /api/v1/conversations/{conversation_id}` requires `app_id` and `page` query
parameters so the service can re-resolve trusted identity and workspace. It
returns `ConversationResponse`:

```json
{
  "conversation": {
    "conversation_id": "conversation:…",
    "owner_user_id": "mock-user-limited-viewer",
    "workspace": {"workspace_id": "workspace_recruiting_alpha", "app_id": "orka_ats"},
    "status": "active"
  },
  "messages": [
    {"role": "user", "content": "Explain this page."},
    {"role": "assistant", "content": "Candidate profile: …", "source_ids": ["candidate_profile"]}
  ]
}
```

An ID belonging to another verified user or workspace returns a non-disclosing
`404 domain_error` response. The app metadata endpoint returns `AppMetadata`.
The feature endpoint returns `FeatureCatalogResponse` with `app` and controlled
catalog `features`; it must not be interpreted as the current user's permission
result.

### Failure examples

No context is a validation failure:

```json
{
  "code": "validation_error",
  "message": "Request validation failed.",
  "details": {"fields": ["body.context"]}
}
```

An unverified trusted session is refused before a conversation or response is
created:

```json
{
  "code": "identity_unverified",
  "message": "Sign-in verification is required before this information can be shown."
}
```

A selected candidate that the adapter denies is not described as missing or
successful:

```json
{
  "code": "candidate_access_denied",
  "message": "The requested candidate information is not available for the verified account."
}
```

Adapter outage or timeout returns no assistant response and no fabricated
conversation/message:

```json
{
  "code": "adapter_unavailable",
  "message": "A required dependency is currently unavailable. No application data was returned."
}
```

All error envelopes also include `schema_version` and `request_id`.
