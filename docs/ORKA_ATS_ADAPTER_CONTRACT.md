# OrkaATS Mapping to the General Adapter Contract

**Status:** Prompt 8 semantic mapping only  
**General contract:** `OrkaApplicationAdapter` `1.0.0`  
**Implementation:** Deferred to Prompt 9

## Scope

OrkaATS implements the general Orka application adapter while retaining authority
over candidates, workspace membership, record and field visibility, recruiting
business rules, action availability, validation, and writes. This document maps
OrkaATS meanings to the application-neutral types. It does not define a real or
mock implementation, fixtures, endpoints, transport, or an executable action.

The general protocol contains no candidate-only request or response field.
Candidate-specific conversion remains inside the OrkaATS adapter/application
mapping and does not leak into registry or core orchestration.

## Identity and context mapping

| General contract value | OrkaATS meaning |
|---|---|
| `app_id` | Stable value `orka_ats`. |
| `UserIdentity` | OrkaATS-verified current user. A role is a label and never grants candidate access by itself. |
| `WorkspaceRef` | Verified recruiting workspace/project scope. Browser-provided workspace IDs remain hints. |
| `page_id` | Verified current OrkaATS page ID. Page access is returned separately in trusted authorization facts. |
| `SelectedEntityRef` | A selected candidate uses `entity_type="candidate"` and an OrkaATS-owned candidate ID. The reference alone grants no visibility. |
| `ResolvedApplicationContext` | Request-scoped verified identity, page, workspace, and optional candidate selection. |

`resolve_current_user` ignores claimed browser email, user ID, roles, permissions,
and actions. An unknown or unverifiable subject produces a claim-free unverified
identity or an explicit unauthorized failure. Sensitive methods require a verified
identity.

`resolve_context` treats the selected candidate and page as hints. OrkaATS verifies
workspace membership and returns a candidate reference only when it can safely
bind the selection. This still does not imply record visibility; explicit
authorization facts remain required.

## Permission and selected-candidate semantics

`get_user_permissions` returns `TrustedAuthorizationFacts` with source
`application_adapter`. For OrkaATS these facts may include:

- explicit app access;
- allowed page IDs;
- namespaced permissions such as `candidate.view`;
- exact candidate record grants and their visible field IDs; and
- action IDs currently available to the user and context.

Omitted facts deny. Record visibility is independent of role. A candidate that is
missing, private, archived, outside the workspace, or otherwise inaccessible may
be returned as the same safe not-found/forbidden outcome; responses must not leak
existence through details.

`get_selected_entity_summary` accepts a generic selected-entity request. The
OrkaATS implementation verifies `entity_type="candidate"`, identity, workspace,
record access, field access, and relevant permission before constructing a
response. It returns:

- the generic candidate reference;
- an optional safe display label;
- only allowed `VisibleEntityField` values with sensitivity labels and closed
  typed values;
- bounded visible/redacted counts; and
- request and adapter-response bindings.

Hidden field IDs and values are absent. Candidate notes are omitted by default.
Any later notes capability must retain the established sensitive,
`untrusted_content`, never-persisted handling and requires a separate approved
permission path. The Prompt 9 implementation may map the generic summary into the
existing request-scoped `CandidateSummary` domain view inside the OrkaATS-specific
boundary; it must not change the general protocol to carry candidate-only fields.

`search_allowed_records` searches only candidate records already allowed for the
verified identity/workspace. It enforces the general maximum result limit and
returns minimal labels plus explicitly requested, visible fields. It cannot return
full candidate objects, hidden fields, unrestricted exports, or opaque arbitrary
payloads.

## Page, feature, event, and action availability

`get_page_metadata` maps the verified OrkaATS page to bounded title, purpose,
version, feature IDs, and an internal safe reference. Product guidance and action
definitions remain in controlled catalogs; adapter metadata does not replace
those sources.

`get_available_features` returns only feature IDs OrkaATS considers available in
the current verified context. Catalog membership alone does not make a feature
available.

`get_recent_user_events` returns a bounded list of meaningful OrkaATS events. It
must not return raw navigation streams, keystrokes, unrestricted candidate
content, or sensitive notes. Entity references are included only when permitted.

`get_available_actions` returns current OrkaATS action availability as IDs. An ID
is necessary but not sufficient for execution. OrkaFin also requires an active
matching `ActionDefinition`, explicit permission, candidate visibility, preview,
confirmation, and execution-time revalidation.

## Approved action semantics

Prompt 8 defines no enabled OrkaATS action. If a later prompt enables one,
`execute_approved_action` is the only adapter operation that may mutate candidate
business state. The request must include:

- the active versioned action definition;
- current OrkaATS-verified identity and context;
- a confirmed proposal bound to the candidate and exact parameters;
- accepted one-time confirmation state;
- the idempotency key; and
- the execution request ID.

OrkaATS revalidates candidate visibility, action permission and availability,
current candidate state, action/version, parameters, and business rules. A
successful response requires an `AdapterExecutionReceipt` matching `orka_ats`,
the action, candidate target, execution request, and idempotency key, with an
OrkaATS transaction/reference ID and UTC timestamps.

A conflict, validation failure, denial, unavailable dependency, timeout, malformed
receipt, or internal failure remains explicit. In particular, a timeout after an
execution attempt is an ambiguous outcome until reconciled; OrkaFin must not claim
success or claim that no change occurred without authoritative evidence.

`log_feedback` is optional and non-authoritative. It may deliver feedback about an
OrkaFin recommendation but cannot update a candidate, grant permission, execute an
action, or act as an alternate candidate-write path.

## Prompt 9 implementation obligations

The mock OrkaATS adapter should implement this mapping with synthetic data only
and pass `tests.contracts.adapter_contract.assert_adapter_contract`. In addition,
its tests must prove:

- forged browser identity, role, permission, record, field, and action claims do
  not broaden access;
- private or missing candidates do not leak;
- selected summaries and search results are field-filtered inside the adapter;
- candidate notes cannot become instructions and remain omitted by default;
- every advertised optional capability enforces its declared limits;
- deterministic simulated failures map to the typed adapter errors; and
- unsupported or disabled action execution returns an explicit failure, never a
  fabricated receipt.

Prompt 9 may add OrkaATS-only packages and synthetic fixtures. It must preserve the
general method names/signatures, error classes, registry mechanism, and reusable
contract-suite entry point established here.
