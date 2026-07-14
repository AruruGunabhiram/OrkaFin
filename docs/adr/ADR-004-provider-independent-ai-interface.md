# ADR-004: Provider-Independent AI Interface

- **Status:** Accepted — implemented in Prompt 13
- **Date:** 2026-07-14
- **Decision owners:** OrkaFin engineering, product, and security
- **Scope:** Response generation and external-model authority

## Context

Local V1 needs reliable grounded responses in automated tests and demonstrations.
Binding product behavior to an external model would introduce credentials, network
availability, variable output, data handling, cost, and model-version changes.
More importantly, natural-language output must never become the source of
permissions, feature existence, action availability, or write success.

An optional model may make wording more natural, but the application must define
and validate what facts and response types are allowed.

## Decision

Define a typed provider-independent response interface with a deterministic local
implementation as the default. Its input is a bounded structured object containing
the user question, validated intent classification, permitted redacted context,
retrieved source excerpts, and response constraints. Its output is a typed response
draft with claims tied to supplied source IDs.

All tests and the full local demo run with no external key or network access. A
later external provider is optional and selected by explicit configuration. It may
improve wording or summarize only the supplied minimized, permitted, grounded
facts. Application services validate its output and fall back to deterministic
behavior when safe.

Providers cannot:

- resolve identity or decide application/record/field/action permission;
- create a feature, source, action definition, or parameter outside typed catalogs;
- call adapters, write repositories, consume confirmation, or execute actions;
- receive raw candidate rows, hidden fields, full candidate notes, secrets, raw
  audits, or unrestricted conversation history;
- represent action success without a schema-valid owning-adapter receipt.

Candidate notes are excluded from provider input by default. Retrieved help text,
user questions, and prior messages remain untrusted data, not instructions.

## Provider boundary

Application services own permission checks, grounding selection, response-type
selection, action state, and receipt validation on both sides of the interface.
The provider has no repository or adapter dependency. This boundary applies to the
deterministic implementation and every optional external implementation.

## Consequences

Positive consequences:

- Reproducible offline tests/demo and predictable safe fallbacks.
- Model vendor/version can change behind one contract.
- Permission, retrieval, action, and receipt rules remain ordinary testable code.
- Provider input can be inspected and minimized consistently.

Costs and limitations:

- Deterministic wording may be less fluent and cover fewer paraphrases.
- Typed response validation and provider adapters require deliberate schema work.
- A model response may need rejection, repair within bounded rules, or fallback.
- Provider independence is limited by the common contract; vendor-specific features
  need explicit justification rather than leaking into core services.

## Alternatives considered

**Require one external model:** rejected because it makes tests/demo dependent on
secrets/network and encourages model-owned product behavior.

**Use model tool calling for permissions/actions:** rejected because tools cannot
replace server authorization, confirmation, adapter validation, or receipts.

**No model interface at all:** deterministic generation alone is sufficient for
mandatory V1, but an interface keeps optional wording experiments replaceable and
auditable. Rejected as a permanent restriction.

**Adopt LangChain/LangGraph/multi-agent framework:** rejected for V1 because the
workflow is explicit, bounded, and easier to audit as native typed services.

## Failure behavior

Provider configuration is disabled by default. Missing keys in deterministic mode
are normal. External provider timeout, malformed output, uncited claim, unknown
feature/action, policy-like instruction, or unsafe content cannot broaden the
response. The service uses a grounded deterministic fallback where possible or a
safe unavailable response. Logs record provider category/timing and safe error
code, not secrets or raw sensitive prompts.

## Verification

- Run the full unit, security, integration, and end-to-end suite with provider
  credentials absent and network calls blocked.
- Contract-test deterministic and optional provider adapters against the same
  strict input/output schema.
- Inspect provider input fixtures to prove hidden fields, notes, secrets, and raw
  audits are absent.
- Adversarially request fabricated features, permissions, and success; validation
  must reject them.
- Inject instructions into user/help/note/history fields; no permission/action
  state changes and no hidden markers appear.
- Simulate provider timeout/malformed output and assert deterministic fallback or
  safe unavailable behavior.
- Require a valid adapter receipt in the domain model before an execution success
  response can exist.

## Change triggers

Adding a provider, sending a new data category, enabling tool use, depending on a
provider-only feature, or removing deterministic fallback requires review. A
superseding ADR must document provider terms/retention/location, data inventory,
evaluation quality and safety results, cost/latency limits, key management,
timeouts, output validation, outage behavior, model/version change process, and
rollback. Models never become authorization or write authorities under a routine
provider change.
