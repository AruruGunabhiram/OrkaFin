# General Orka Application Adapter Contract

**Status:** Prompt 8 application-neutral contract  
**Wire schema version:** `v1`  
**Adapter contract version:** `1.0.0`

## Purpose and authority boundary

`OrkaApplicationAdapter` is the only application-data boundary used by OrkaFin.
Each Orka application remains authoritative for its identity assertions, records,
record and field visibility, business rules, action availability, validation, and
writes. OrkaFin orchestrates these capabilities but cannot broaden a returned
grant, substitute browser claims, or infer a successful write.

The contract is application-neutral. It uses `SelectedEntityRef`,
`WorkspaceRef`, bounded visible fields, namespaced permissions, and catalogued
action IDs. It exposes neither an unrestricted query/storage handle nor a generic
`call(name, payload)` escape hatch. Transport and operational storage details are
implementation-private.

Every structured request, response, nested payload, failure, and receipt is a
strict Pydantic model with `schema_version="v1"`. Every request and operation
response also carries `adapter_contract_version="1.0.0"`, `request_id`, and
`app_id`. Responses add `adapter_response_id` and a UTC `responded_at` timestamp.

## Public interface

The protocol lives at `orkafin.adapters.base.OrkaApplicationAdapter`. All methods
are asynchronous and explicitly typed:

| Capability | Signature | Responsibility |
|---|---|---|
| `get_app_metadata` | `GetAppMetadataRequest -> GetAppMetadataResponse` | Return bounded app identity, version, status, and contract version. |
| `resolve_current_user` | `ResolveCurrentUserRequest -> ResolveCurrentUserResponse` | Resolve identity from trusted server/transport input; browser hints never establish identity. |
| `resolve_context` | `ResolveContextRequest -> ResolveContextResponse` | Verify current page, workspace, and optional selected entity for a trusted identity. |
| `get_user_permissions` | `GetUserPermissionsRequest -> GetUserPermissionsResponse` | Return fresh `TrustedAuthorizationFacts` for deny-by-default evaluation. |
| `get_page_metadata` | `GetPageMetadataRequest -> GetPageMetadataResponse` | Return bounded metadata for the verified current page. |
| `get_selected_entity_summary` | `GetSelectedEntitySummaryRequest -> GetSelectedEntitySummaryResponse` | Return only explicitly visible fields for the verified selected entity. |
| `get_available_features` | `GetAvailableFeaturesRequest -> GetAvailableFeaturesResponse` | Return IDs of features available in the current trusted context. |
| `get_available_actions` | `GetAvailableActionsRequest -> GetAvailableActionsResponse` | Return current action availability; it does not define or execute actions. |
| `get_recent_user_events` | `GetRecentUserEventsRequest -> GetRecentUserEventsResponse` | Return a bounded window of meaningful, privacy-minimized app events. |
| `search_allowed_records` | `SearchAllowedRecordsRequest -> SearchAllowedRecordsResponse` | Search only records and fields the current identity may view, with a hard result limit. |
| `execute_approved_action` | `ExecuteApprovedActionRequest -> ExecuteApprovedActionResponse` | Revalidate and execute one fully bound catalogued action and return an explicit receipt. |
| `log_feedback` | `LogFeedbackRequest -> LogFeedbackResponse` | Deliver a replay-protected, non-authoritative feedback signal. |

The first five capabilities are mandatory in contract `1.0.0`. The remaining
capabilities are optional because an application may have no selectable records,
events, search, actions, or feedback sink. Every method still exists on the
protocol. An unadvertised method must raise
`AdapterUnsupportedCapabilityError`; it must not return an empty success merely
to hide non-support.

`AdapterMetadata` declares `adapter_id`, `owning_app_id`, adapter and contract
versions, and an independently versioned set of `AdapterCapabilityMetadata`.
Duplicate capabilities and omission of a mandatory capability are schema errors.

## Trust and read rules

`ClientContextHint` remains untrusted even when it is passed to an adapter. The
adapter routes and verifies hints against its own authority. It must never copy
claimed role, email, permissions, available actions, workspace, or record access
into a trusted response without independent verification.

With the exception of public app metadata and identity establishment, sensitive
calls use `TrustedAdapterRequest` or `ContextBoundAdapterRequest`. These schemas
require:

- a verified `UserIdentity` whose role owner matches the routed app;
- a `ResolvedApplicationContext` for the same identity and app; and
- a propagated request ID.

The owning adapter filters before returning data. `SelectedEntitySummary` and
`AllowedRecordSearchResult` contain only visible, typed fields. Hidden field IDs
and values are absent; only bounded redaction counts may be returned. Search has
a maximum request limit of 50 and cannot request arbitrary response shapes.

`get_user_permissions` returns the already approved
`TrustedAuthorizationFacts` interface with source
`application_adapter`. Missing facts deny. Roles label identity but do not create
grants. `get_available_actions` returns IDs only; an active, versioned
`ActionDefinition` remains separately controlled by the product catalog.

## State-changing action rule

`execute_approved_action` is the sole contract operation allowed to change an
owning application's business records. `ExecuteApprovedActionRequest` requires
all of the following and rejects mismatched bindings before an implementation is
called:

- an active `ActionDefinition`;
- the current verified identity and freshly resolved context;
- a confirmed `ActionProposal` for the selected target;
- an accepted `ActionConfirmation` bound to proposal, user, workspace, and
  parameter hash;
- the exact idempotency key; and
- the execution request ID.

The owning application must re-check identity, visibility, permission, current
state, action/version, parameters, and business rules. Success is representable
only by a schema-valid `AdapterExecutionReceipt`. The receipt includes adapter and
owning-app IDs, action ID/version, generic target reference, execution and receipt
timestamps, request ID, idempotency key, outcome, and an adapter transaction or
reference ID. A failed receipt requires a safe failure code. A timeout, malformed
receipt, or exception is never converted into success.

`log_feedback` is not an alternate write/action channel. It may acknowledge a
non-authoritative feedback signal, but a conforming implementation must not use it
to mutate application records, bypass an action definition, or claim action
success. Its idempotency key protects delivery retries.

## Explicit failures

Adapters return or map only these stable failure categories:

| Code / exception | Retryable | Meaning |
|---|---:|---|
| `unavailable` / `AdapterUnavailableError` | Yes | Configured application dependency is unavailable. |
| `unauthorized` / `AdapterUnauthorizedError` | No | Trusted application identity could not be established. |
| `forbidden` / `AdapterForbiddenError` | No | Identity is known but this operation or scope is denied. |
| `not_found` / `AdapterNotFoundError` | No | Resource is absent or safely indistinguishable from inaccessible. |
| `validation_failed` / `AdapterValidationFailedError` | No | Typed input or owning-app business validation failed. |
| `conflict` / `AdapterConflictError` | No | Current authoritative state conflicts with the request. |
| `timeout` / `AdapterTimeoutError` | Yes | No definitive outcome was received before the deadline. |
| `internal_failure` / `AdapterInternalFailureError` | No | Owning application reported an internal failure. |
| `unsupported_capability` / `AdapterUnsupportedCapabilityError` | No | Operation is not advertised by this adapter. |

`AdapterFailure` is the versioned safe failure schema.
`adapter_error_from_failure` maps it to the exact typed exception without exposing
transport payloads or exception text. Retryable means a caller may apply an
operation-specific retry policy; it does not permit blind retries of ambiguous
writes. Idempotency/reconciliation rules still control action retries.

## Dependency injection and resolution

`AdapterRegistry` receives `AdapterRegistration(app_id, factory)` values through
dependency injection. It lazily creates and caches one adapter instance per app,
checks structural protocol conformance, verifies app and contract metadata, and
can require a capability during resolution. Missing registrations, duplicate
registrations, metadata mismatch, factory failure, and unsupported capabilities
produce explicit typed errors.

`ApplicationDependencies.adapter_registry` is built with an empty registry by
default and accepts an injected configured registry through `build_dependencies`.
There is no global mutable registry. An empty registry means application-backed
facts are unavailable; callers may not fall back to browser claims or a model.

## Onboarding another Orka application

1. Define the app's stable `app_id`, adapter version, mandatory capability
   versions, and only the optional capabilities it really supports.
2. Implement every named async protocol method. Unadvertised optional operations
   must raise `AdapterUnsupportedCapabilityError`.
3. Map app records to generic `SelectedEntityRef` values and return only
   permission-filtered `VisibleEntityField` values. Keep app-specific record
   schemas inside the adapter package.
4. Resolve identity and authorization from a trusted application/server boundary.
   Treat every `ClientContextHint` claim as untrusted.
5. Keep operational record access and business rules private to the application.
   Do not expose raw query clients, repositories, storage coordinates, or
   unrestricted payload dictionaries.
6. If actions are supported, accept only `ExecuteApprovedActionRequest`, revalidate
   authoritatively, enforce idempotency, and return a matching receipt or typed
   error.
7. Register an injected factory for exactly one app ID; never add app-specific
   branches to core orchestration.
8. Run the reusable suite at
   `tests.contracts.adapter_contract.assert_adapter_contract` with a synthetic
   `AdapterContractScenario`, plus implementation tests for every advertised
   optional capability, filtering, failures, and receipt behavior.

Passing the contract suite proves local schema and behavior conformance only. It
does not prove production authentication, transport integrity, data policy, or an
owning application's business rules.

## Compatibility rules

- Wire schema `v1`, adapter contract `1.0.0`, and each capability version evolve
  independently.
- An incompatible contract version fails registration/resolution; it is not
  silently coerced.
- Additive capability support is advertised in metadata. Removing or changing a
  capability requires compatibility review and contract tests.
- Existing domain and permission interfaces remain unchanged. App-specific
  adapters map to them rather than renaming them.
- A new public operation requires a contract-version decision; it cannot be added
  through a generic payload dispatch method.
