# AI Provider Model

## Purpose and trust boundary

Response providers are optional phrasing components downstream of trusted context
resolution and deterministic retrieval. They do not authenticate users, evaluate
permissions, select features or actions, read adapters, execute writes, or report
action success. `ResponseGenerationService` selects the response intent and allowed
content kind, validates provider drafts, and constructs `AssistantResponse`.

The default is `DeterministicResponseProvider`. It is offline, template-based, and
supports the complete local V1 demo and test suite with no model key. Its stable
template IDs are:

- `explain_page_v1`
- `available_actions_v1`
- `step_by_step_help_v1`
- `candidate_summary_v1`
- `refusal_verified_access`
- `unknown_no_approved_source`
- `uncertainty_grounded_v1`

The other template IDs describe bounded unavailable or safe-failure cases.

## Provider input allowlist

Every `ResponseProvider` receives only `ProviderRequest`:

- the bounded user question;
- app display name, page ID, and selected entity type;
- standard fields from an already-authorized candidate summary, when applicable;
- source ID, title, and a maximum 500-character approved retrieved excerpt;
- server-selected intent and response constraints.

The provider never receives an identity, email, role, workspace ID, permission
list, action list, candidate ID, raw database row, hidden field, restricted or
sensitive candidate field, candidate note, secret, credential, audit log, or
conversation history. Candidate-summary output remains unavailable unless a
candidate-summary source was separately approved and supplied.

## Grounding and fallback

The response service checks that the provider chose an allowed content kind, cited
only supplied source IDs, supplied citations whenever grounding is required, and
introduced no novel substantive terms beyond the approved payload. The latter is a
deliberately conservative lexical guard against invented feature names. A grounded
draft becomes an `AssistantResponse` only after its citations and supplied sources
pass the existing domain validator.

Timeouts, transport errors, malformed JSON, unknown or missing citations, output
outside the selected kind, invented terms, and any other provider exception fall
back to deterministic templates. If even that fallback cannot validate, the result
is a safe unavailable response. Provider error detail, payloads, credentials, and
model output are not returned or logged.

## Optional external adapter

`OpenAICompatibleResponseProvider` is the sole optional adapter. It is selected
only when all of these server-side environment values are valid:

- `ORKAFIN_AI_PROVIDER=external`
- `ORKAFIN_AI_PROVIDER_API_KEY`
- `ORKAFIN_AI_PROVIDER_BASE_URL` (HTTPS only)
- `ORKAFIN_AI_PROVIDER_MODEL`
- `ORKAFIN_AI_PROVIDER_TIMEOUT_SECONDS` (optional; default `5`)

The adapter sends the same minimized `ProviderRequest` and asks for a JSON draft;
it cannot receive repositories, adapters, or permission services. Its transport is
injected in tests, so the suite makes no live provider call. This adapter is a
minimal V1 integration and is **not production-ready**: production use would need
provider terms/retention review, key management, outage monitoring, model-version
governance, and a security review.

## Why a model is optional

The authoritative behavior is deterministic retrieval plus schema validation. A
model can make wording less rigid but cannot improve authority or grounding. Keeping
the model optional preserves reproducible local testing, safe offline demonstrations,
and a straightforward rollback path to deterministic templates.
