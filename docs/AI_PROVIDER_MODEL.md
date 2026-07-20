# AI Provider Model

**Status:** Prompt 20 adversarially reverified for the Local V1 provider boundary

## Purpose and authority boundary

Response providers are optional phrasing components downstream of trusted context
resolution and deterministic retrieval. They do not authenticate users, evaluate
permissions, select candidate visibility, create features or actions, call adapters,
execute writes, or report action success. `ResponseGenerationService` owns input
minimization, intent and ID allowlists, output validation, fallback, and construction
of `AssistantResponse`.

The offline `DeterministicResponseProvider` remains the default. The local demo and
test suite require no model key or network access. An external provider receives the
same minimized contract and is an untrusted dependency, not another authority.

## Prompt contract 1.0.0

Code-owned Prompt 14 templates are version `1.0.0` and are selected by the server,
never by user or retrieved text:

| Intent | Prompt template ID |
|---|---|
| Explain page | `explain_page_v1` |
| Available actions | `available_actions_v1` |
| Step-by-step help | `step_by_step_help_v1` |
| Candidate summary | `candidate_summary_v1` |
| Refusal | `refusal_v1` |
| Unknown | `unknown_v1` |
| Uncertainty | `uncertainty_v1` |

The external adapter sends three roles in fixed order: a shared system policy, the
intent-specific developer template, and one JSON user message containing only
trust-tagged data. Untrusted strings are JSON encoded and never interpolated into
the system or developer messages. The compact JSON data message has these sections:

- `verified_context`: server-resolved app, page, selected entity type, and any
  separately permitted candidate-summary fields;
- `approved_sources`: source ID/type, title, bounded excerpt, verification state,
  verified structured steps, and server-approved feature/action IDs;
- `untrusted_user_question`: question data, explicitly not evidence or instruction;
- `untrusted_conversation_history`: bounded user-visible data, not evidence;
- `forbidden_behaviors`: a lower-priority mirror of the authoritative system policy;
- `output_contract`: allowed response kinds, source/feature/action/receipt IDs, and
  the step limit.

Source excerpts, help text, user text, prior assistant text, and candidate values
remain data even if they contain phrases such as “ignore previous instructions.”
The system and developer rules require structured output but are not treated as a
complete prompt-injection solution.

## Intentional internal contract hardening

The domain `schema_version` remains `v1`; the public assistant endpoint is
`POST /api/v1/assistant/queries`. The final internal provider contract intentionally
tightens the earlier draft shape:

- every grounded `ProviderDraft` now requires `ProviderClaim` records covering its
  main text and every step exactly once;
- every claim declares a closed claim kind, exact output location/text, source IDs,
  and any feature/action/receipt IDs;
- `ApprovedProviderSource` now carries source type, verification status, verified
  structured steps, and source-backed feature/action IDs;
- `SafeResponseConstraints` now carries server-built feature/action/receipt
  allowlists; and
- `ProviderRequest.history` is an additive, bounded list of explicitly untrusted,
  user-visible messages.

An external adapter written against the Prompt 13 draft shape must add structured
claims before it is compatible with contract 1.0.0. This breaking internal output
change is deliberate: accepting an old grounded draft without claim mappings would
reopen the ambiguity Prompt 14 removes.

The deterministic response template IDs remain stable where their behavior remains
available: `explain_page_v1`, `available_actions_v1`, `step_by_step_help_v1`,
`candidate_summary_v1`, `refusal_verified_access`, `unknown_no_approved_source`, and
`uncertainty_grounded_v1`. Additional IDs identify explicit unavailable or final
safe-failure paths.

## Provider input minimization

`ProviderRequest` contains at most a 500-character question, 10 source excerpts of
at most 500 characters each, 25 safe candidate fields, and bounded conversation
history. It never contains email, role, workspace ID, permission names, candidate
ID, raw database rows, hidden/restricted candidate fields, candidate notes, secrets,
credentials, raw adapter payloads, audits, or hidden system/developer messages.

Candidate fields cross the boundary only for `candidate_summary` when the resolved
context has an adapter-backed summary and the retrieval result includes a
`candidate_summary` source. Standard fields are further bounded; notes and restricted
fields remain excluded. Other intents receive no candidate fields even if the
resolved context happens to contain them.

Raw help Markdown remains searchable controlled data, but it is not provider
evidence. Only the separately bounded article summary and human-verified structured
`instruction_steps` may cross the provider boundary. This reduces the effect of an
injected article body without claiming that a malicious approved summary is safe.

`BoundedConversationHistoryPolicy` admits only server-classified, provider-safe
`user` and `assistant` entries. It drops `system`/`developer` roles and entries marked
sensitive, content-redacts recognizable email/credential values, then keeps the
newest data within 6 messages, 300 characters per message, and 1,200 characters
total. History can help continuity but is never grounding. The assistant derives
history from server-owned persisted `Message` records; clients cannot submit a
history role or `sensitivity` classification.

## Output validation and grounding

The public internal validation entry point for the next prompt is:

```python
ProviderOutputValidator.validate(draft: ProviderDraft, request: ProviderRequest) -> None
```

`ProviderOutputAllowlist.from_request()` exposes the exact allowed response kinds,
source IDs, feature IDs, action IDs, and receipt IDs for inspection. Validation
rejects duplicate/unknown citations, unallowed kinds or IDs, excessive steps,
claims that do not exactly cover output fields, and claim citations that differ
from response citations.

`ClaimGroundingChecker` enforces the V1 category mappings:

- product facts require approved app/page catalog evidence;
- feature facts require explicit allowed feature IDs backed by supplied feature
  sources;
- help facts require an approved help source;
- candidate facts require supplied standard fields and a candidate-summary source;
- action suggestions require an allowed action ID backed by an action-definition
  source that survived current-context action filtering; and
- steps must exactly match a source's human-verified `approved_steps` entry.

The checker also applies a conservative lexical comparison against only the cited
source and verified context. User questions and history are deliberately excluded
from the approved vocabulary. This comparison is defense in depth, not the primary
control, and may reject legitimate paraphrases.

Provider drafts cannot author `action_success`, even if they supply a plausible
receipt ID. Action outcome belongs to the separate typed `ActionExecutionResult`
path, whose success state requires a matching successful `AdapterExecutionReceipt`.
If future UI prose reports that result, application code must construct it directly
from the validated result rather than asking a model to attest it.

## Rejection and fallback

Timeouts, malformed JSON, missing structured claims, fake citations, invented IDs,
unsupported terms or steps, unauthorized action suggestions, action-success claims,
and any provider exception first fall back to the deterministic provider using the
same minimized request and validator. If that output also fails, the service returns
a fixed unavailable response with no sources. Provider error details and rejected
raw output are not returned or logged.

Unknown features, absent sources, unverified step lists, unavailable candidate
summary sources, and empty authorized-action allowlists select an unavailable kind
before generation. If an explain-page request has sources but none are verified,
the server downgrades the provider intent to `uncertainty`, whose deterministic
template says the approved guidance is limited. A claim citing a non-verified source
under a non-uncertainty intent is rejected. The fallback therefore cannot broaden
the original request or silently turn provisional guidance into verified fact.

## Optional external adapter

`OpenAICompatibleResponseProvider` remains disabled unless all required server-side
settings are valid:

- `ORKAFIN_AI_PROVIDER=external`
- `ORKAFIN_AI_PROVIDER_API_KEY`
- `ORKAFIN_AI_PROVIDER_BASE_URL` (HTTPS only)
- `ORKAFIN_AI_PROVIDER_MODEL`
- `ORKAFIN_AI_PROVIDER_TIMEOUT_SECONDS` (optional; default `5`)

Its transport is injected in tests, so the suite makes no live provider call. The
adapter remains a minimal local integration, not production-ready.

## Residual risks requiring human review

- Structured claims prove an allowlisted mapping, not semantic truth or full textual
  entailment. A model may produce a misleading paraphrase using allowed vocabulary.
- The narrow success-phrase recognizer is defense in depth and can miss novel
  wording or reject benign language; no keyword list can solve injection generally.
- A malicious or erroneous approved summary can still ground bad guidance. Catalog
  review, provenance, and rollback remain required; schema validation is not content
  review.
- Raw help content still affects deterministic retrieval matching even though it is
  excluded from provider evidence, so poisoned text can affect ranking or cause a
  safe but irrelevant result.
- All current user-visible messages are treated as provider-safe untrusted history
  after finite content-pattern redaction. Semantically sensitive text not recognized
  by those patterns may still cross the optional provider boundary. Truncation can
  also remove qualifying context and cause safe false negatives.
- Candidate-source binding relies on trusted internal orchestration and the existing
  resolved-context adapter evidence. Future source construction must preserve that
  binding and must not accept client-created `RetrievedSource` objects.
- External-provider retention, data location, model updates, account compromise,
  prompt confidentiality, and availability have not been reviewed.
- The red-team fixtures are finite examples, not a penetration test, proof of complete
  prompt-injection prevention, or evidence of production security.

Prompt 20 exercises this contract and its fallback behavior without a live provider.
Its false-negative tradeoff and the residual risks above still require human
acceptance before the provider or deployment boundary expands.
