# Local V1 API

## Trusted context resolution

`POST /api/v1/contexts:resolve` converts browser hints into request-scoped facts
verified by the configured owning-application adapter. The `:resolve` action name
is intentional: the call performs verification and returns an ephemeral value; it
does not create or update a durable `context` resource. The `/api/v1` prefix fixes
the public contract version independently of internal package versions.

The request body is exactly `ClientContextHint`. No header or body field selects a
trusted user. The application composition root supplies a `TrustedSessionResolver`
from server/session state. The default resolver returns no subject and therefore
fails closed. `StaticTrustedSessionResolver` is a synthetic test harness only.

Example request (all claims remain untrusted):

```json
{
  "schema_version": "v1",
  "app_id_hint": "orka_ats",
  "page_id_hint": "candidate_profile",
  "workspace_id_hint": "workspace_recruiting_alpha",
  "selected_entity_hint": {
    "schema_version": "v1",
    "app_id_hint": "orka_ats",
    "entity_type_hint": "candidate",
    "entity_id_hint": "CAND-1042"
  },
  "claimed_user_id": "forged-admin-user",
  "claimed_email": "forged.admin@example.invalid",
  "claimed_role_ids": ["administrator"],
  "claimed_permissions": ["candidate.update_start_date"],
  "claimed_available_action_ids": ["candidate.update_start_date"],
  "client_request_id_hint": "00000000-0000-4000-8000-000000000999"
}
```

The server request ID comes from request middleware; `client_request_id_hint` does
not replace it. With the trusted synthetic session fixed to `limited_viewer`, the
important portion of the response is:

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
| 403 | `context_access_denied` | Trusted app/page facts deny access; no claimed grant is echoed |
| 403 | `candidate_access_denied` | Exact candidate/permission check failed; candidate existence and fields are not disclosed |
| 422 | `validation_error` | Request shape failed bounded validation; only field locations are returned |
| 503 | `adapter_unavailable` | Unknown app/page, unavailable capability, timeout, or adapter failure; message states that no application data was returned |
| 500 | `internal_error` | Unexpected safe failure; no exception content or candidate data |

The endpoint performs no answer generation, recommendation, action proposal,
confirmation, or write.

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

## Prompt 11 human review checkpoint

Prompt 12 must not begin until a human reviewer approves or requests changes to:

- the separation between the untrusted request and trusted session subject;
- the top-level and per-component trust/source labels;
- the limited-viewer redacted candidate example;
- the 401/403/503 response codes and non-disclosing messages; and
- the audit target reference plus minimized detail fields described above.

| Review field | Value |
|---|---|
| Reviewer | Pending |
| Review date | Pending |
| Outcome | Pending: approve, approve with conditions, or request changes |
| Conditions/changes | Pending |
