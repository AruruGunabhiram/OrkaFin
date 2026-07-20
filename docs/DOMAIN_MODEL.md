# OrkaFin Local V1 Domain Model

**Status:** Prompt 4 canonical contracts; review required before Prompt 5 persistence
**Wire schema version:** `v1`

## Purpose and contract rules

The public contracts under `src/orkafin/domain` are the types later persistence,
adapters, services, providers, endpoints, and tests must use. They define data
shape and invariants only. This increment does not implement authorization,
retrieval, adapter calls, action workflows, or SQL persistence.

All structured models:

- are Pydantic v2 models with frozen values, strict Python validation, forbidden
  extra fields, validated defaults, and an explicit `schema_version` of `v1`;
- expose immutable `data_policy` class metadata with the authoritative owner,
  maximum classification, persistence rule, and per-field handling requirements;
- accept supported string enum values on JSON boundaries but reject unknown enum
  values and implicit Python coercion;
- use bounded IDs, text, collections, metadata, and safe internal references;
- accept timestamps only when timezone-aware with UTC offset `+00:00`/`Z`;
- use closed typed values or discriminated unions instead of arbitrary payload
  dictionaries.

`data_policy` is code-controlled metadata, not a client-editable payload field.
Callers cannot relabel client claims as adapter-owned data by changing JSON.

## Public module paths

| Module | Public contracts |
|---|---|
| `orkafin.domain.identifiers` | `RequestId`, `CorrelationId`, `Permission`, `SafeReference`, `Sha256Digest`, `IdempotencyKey` |
| `orkafin.domain.context` | `AppMetadata`, `ClientContextHint`, `ClientSelectedEntityHint`, `ResolvedPageContext`, `ResolvedUserIdentity`, `UserIdentity`, `IdentityVerificationStatus`, `Role`, `WorkspaceRef`, `SelectedEntityRef` |
| `orkafin.domain.candidate` | `CandidateSummary`, visible typed candidate fields, redaction summary, optional sensitive notes excerpt |
| `orkafin.domain.catalog` | `FeatureCatalogItem`, `PageCatalogItem`, `HelpArticle`, catalog provenance and lifecycle enums |
| `orkafin.domain.events` | `UserEvent` and the meaningful-event allowlist |
| `orkafin.domain.recommendations` | `Recommendation`, `RecommendationFeedback` and lifecycle/feedback enums |
| `orkafin.domain.conversations` | `Conversation`, `Message` and their closed status/role enums |
| `orkafin.domain.sources` | `RetrievedSource`, `SourceType` |
| `orkafin.domain.responses` | `GroundingStatus`, `AssistantResponse`, and discriminated response content |
| `orkafin.domain.actions` | `ActionDefinition`, `ActionProposal`, `ActionConfirmation`, `AdapterExecutionReceipt`, `ActionExecutionResult` |
| `orkafin.domain.audit` | `AuditRecord` and allowlisted event/outcome enums |
| `orkafin.domain.errors` | `ApiError`, `ErrorCode`, `SafeErrorDetails` |

The same primary names are re-exported from `orkafin.domain`. `ApiError` and
`ErrorCode` remain importable from `orkafin.core.errors` for compatibility; their
JSON envelope is unchanged.

## Ownership and persistence boundary

| Contract/data | Authority | Classification and handling | Persistence rule |
|---|---|---|---|
| `ClientContextHint` | Browser/client | Confidential and wholly untrusted; only app/page navigation and optional entity selection are accepted | Never persist as authority; do not copy raw hints into logs |
| `AppMetadata`, `Role`, `WorkspaceRef`, `SelectedEntityRef`, `UserIdentity`, `ResolvedUserIdentity`, `ResolvedPageContext` | Owning application; local fixture only simulates it | Identity, permissions, entity IDs, and workspace facts are confidential/restricted; verified email stays internal and is absent from `ResolvedUserIdentity` | Request-scoped only; re-resolve before state change |
| `Permission` | Owning application | Confidential namespaced authorization fact | Request-scoped; no browser claim can create one |
| `CandidateSummary` and visible candidate field values | OrkaATS | Restricted; minimize and redact from logs | Request-scoped only; never an OrkaFin candidate table or durable row replica |
| `CandidateNotesExcerpt` | OrkaATS | Restricted, sensitive, and untrusted content; omitted by default, never logged or persisted | Never persist |
| Feature/page/help catalogs and action definitions | Product documentation owner | Internal controlled content; help text remains data, not instruction | Version-controlled catalog files |
| `RetrievedSource` | Source declared; checked against source type | Excerpts may be restricted and must be minimized | Approved references may persist; candidate content must follow its stricter source policy |
| Conversations and messages | OrkaFin | Confidential; bounded visible content, no hidden prompts or raw notes | OrkaFin persistence allowed subject to retention policy |
| Meaningful events, recommendations, feedback | OrkaFin | Confidential; bounded scalar metadata and commentary | OrkaFin persistence allowed; no keystrokes or raw private content |
| Action proposals, confirmation hashes, execution results | OrkaFin | Restricted/secret; parameter and confirmation hashes are internal and redacted | OrkaFin persistence allowed if the optional action is approved |
| `AdapterExecutionReceipt` | Owning application | Restricted application attestation | OrkaFin may persist the minimized receipt |
| `AuditRecord` | OrkaFin | Restricted; actor, target, and details are minimized and not general log content | Append-oriented OrkaFin persistence; no ordinary-user browsing endpoint |
| `ApiError` | OrkaFin | Internal safe message and bounded public details only | Response-only; no traceback or secret payload |

There is deliberately no `Candidate` persistence model. `CandidateSummary` is a
permission-filtered OrkaATS view bound to a request ID and adapter response ID.
Prompt 5 must not turn it into a SQL table or unrestricted JSON snapshot.

## Trust separation

`ClientContextHint` and `ResolvedPageContext` cannot be substituted for one
another:

- The client model accepts only `app_id`, `page`, and optional
  `selected_entity: {type, id}` navigation data. Its internal fixed trust label is
  `untrusted_client_hint`; it is not a client-settable field.
- Client-selected entities use `ClientSelectedEntityHint`; only verified contexts
  use `SelectedEntityRef`.
- Client identity, role, permission, action, workspace, request-ID, and legacy hint
  fields are forbidden rather than represented as claims.
- The resolved model contains typed `Permission` objects, a verification source,
  an adapter response ID, a request ID, `resolved_at`, and `valid_until`.
- Its public `ResolvedUserIdentity` omits the adapter-verified email retained in
  the internal request-scoped `UserIdentity`.
- Its fixed trust label is `verified_for_response_lifetime`.
- A resolved context rejects unverified identities, cross-app workspace/entity
  references, mismatched candidate summaries, duplicate permissions, and candidate
  summaries bound to another request.

Adapter verification is not durable authentication. A later state-changing flow
must resolve identity, permission, visibility, current state, and application
rules again immediately before execution.

## Candidate summary and redaction

`CandidateSummary.visible_fields` is a tuple of closed typed values: text, date,
UTC timestamp, number, or boolean. Each returned field carries its OrkaATS-provided
sensitivity and the literal visibility state `visible`.

The redaction summary reports only safe counts and a stable explanation code. It
does not enumerate hidden field IDs or values. The count must match the visible
field list, and field IDs must be unique.

The default serialized summary does not contain `notes_excerpt`. If an approved
future flow supplies an excerpt, its contract permanently labels the value
`untrusted_content` and `sensitive_candidate_notes`, and requires an explicit
namespaced permission. This contract does not approve candidate-note processing;
that remains a security/ADR change trigger.

Synthetic example:

```json
{
  "schema_version": "v1",
  "candidate_id": "CAND-1001",
  "visible_fields": [
    {
      "schema_version": "v1",
      "field_id": "display_name",
      "label": "Candidate name",
      "sensitivity": "standard",
      "visibility": "visible",
      "value": {
        "schema_version": "v1",
        "kind": "text",
        "value": "Sample Candidate"
      }
    }
  ],
  "visibility": {
    "schema_version": "v1",
    "visible_field_count": 1,
    "redacted_field_count": 2,
    "redaction_applied": true,
    "explanation_code": "field_permissions_applied"
  },
  "source_adapter_response_id": "adapter-response-001",
  "valid_for_request_id": "00000000-0000-4000-8000-000000000001",
  "retrieved_at": "2026-07-13T20:00:00Z"
}
```

## Version, ID, timestamp, and reference conventions

| Value | Convention |
|---|---|
| Wire schema | Literal `v1` on every structured domain model; another or malformed version is rejected |
| Catalog/action content version | Semantic version such as `1.0.0`; independent of wire schema version |
| Revision | 2–64 ASCII alphanumeric/dot/underscore/hyphen characters, such as `rev-001` |
| General external/entity ID | 3–64 characters; starts alphanumeric and then uses ASCII alphanumeric, dot, underscore, colon, or hyphen; uppercase is allowed for owning-app IDs such as `CAND-1001` |
| App/page/feature/action/role ID | Lowercase 3–64 character identifier; dot/underscore/colon/hyphen separators; examples: `orka_ats`, `candidate_profile`, `candidate.update_start_date` |
| Permission | 3–96 lowercase namespaced string with at least one dot, such as `candidate.view`; unknown permission values remain non-authoritative |
| Request/correlation ID | Lowercase canonical 36-character UUID text; wire serialization remains a string |
| Hash | Lowercase 64-character SHA-256 hex digest |
| Idempotency key | 16–128 bounded ASCII identifier characters |
| Safe source reference | Internal `adapter://`, `app://`, `catalog://`, or `knowledge://` URI; credentials, query strings, fragments, and path traversal are rejected |
| Timestamp | Timezone-aware UTC only (`Z` or `+00:00`); non-UTC offsets and naive datetimes are rejected |

Dates such as an action's proposed calendar date are `date` values rather than
timestamps. Their business timezone and partial-date rules remain owned by the
application and unresolved for the optional action.

## Bounded metadata

`BoundedMetadata` is the only general metadata container. It is scalar-only,
limited to 16 entries and 2,048 serialized bytes, uses lowercase safe keys, caps
strings at 256 characters, rejects non-finite numbers, and forbids sensitive key
categories including notes, prompts, tokens, cookies, passwords, email, secrets,
and raw content. `SafeErrorDetails` is separately bounded for public error fields.
Neither accepts `Any`.

## Assistant response and grounding contract

`AssistantResponse.content` is a discriminated union. Its `kind` must match the
mechanical grounding status:

| Content kind | Required grounding status | Required evidence |
|---|---|---|
| `verified_fact` | `verified` | One or more supplied, cited source IDs |
| `grounded_guidance` | `grounded` | One or more supplied, cited approved sources |
| `recommendation` | `grounded` | Recommendation sources must be included and cited |
| `refusal` | `not_applicable` | Stable safe reason code; no authority claim |
| `unavailable_information` | `unavailable` | Stable safe reason code; no guessed answer |
| `action_proposal` | `grounded` | Typed proposal plus a catalogued action-definition source |

Responses reject duplicate sources, unknown citations, missing sources for
grounded kinds, and inconsistent kind/status combinations.

Safe no-answer example:

```json
{
  "schema_version": "v1",
  "response_id": "response-001",
  "conversation_id": "conversation-001",
  "request_id": "00000000-0000-4000-8000-000000000001",
  "grounding_status": "unavailable",
  "content": {
    "schema_version": "v1",
    "kind": "unavailable_information",
    "text": "Approved information is not available for this request.",
    "reason_code": "source_missing"
  },
  "sources": [],
  "created_at": "2026-07-13T20:00:00Z"
}
```

## Action integrity contract

Action definitions use an explicit catalog model and closed parameter types. A
proposal binds action/version, user, workspace, target, exact typed parameters,
SHA-256 parameter hash, request ID, expiration, and idempotency key. Confirmation
stores only a secret hash and remains separate from execution.

`ActionExecutionResult(status="succeeded")` is invalid unless it includes an
`AdapterExecutionReceipt` whose outcome is `succeeded` and whose owner app,
action, version, target, request ID, and idempotency key all match the result. A
successful receipt paired with a non-success result is also rejected. Failure,
conflict, rejection, and ambiguous `unknown` remain explicit states.

Prompt 18 now uses these proposal/confirmation contracts for the selected
mock-only action. It adds no execution result: accepted confirmation ends at
`proposal=confirmed`, `confirmation=accepted`, and `execution_state=not_started`.
Q-007 in `docs/DECISIONS.md` still blocks action-specific execution business rules,
receipt semantics, and a real write.

## Prompt 5 handoff and unresolved choices

Prompt 5 may persist only OrkaFin-owned `Conversation`, `Message`, `UserEvent`,
`Recommendation`, `RecommendationFeedback`, action state (if retained for the
optional later flow), execution receipts, and `AuditRecord`. Persistence adapters
must accept validated domain objects and retain their `v1` schema version where
evolution requires it.

Still unresolved and not hard-coded here:

- authoritative OrkaATS stage IDs/transitions (Q-001);
- the production field inventory, field-name sensitivity, and role/visibility
  matrix (Q-002 and Q-003);
- production identity and adapter authentication (Q-004 and Q-005);
- the selected action's execution business/receipt semantics (Q-007); Prompt 18
  includes confirmation-only preparation under D-028;
- retention/deletion periods and allowed final event metadata (Q-008, Q-010,
  Q-012).

The next human checkpoint in the implementation pack remains after Prompt 7.
Prompt 5 itself must run migration checks that prove no candidate table or durable
candidate-summary replica exists.
