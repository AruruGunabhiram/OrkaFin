# Future Orka App Onboarding Guide

This guide explains how a future Orka application joins OrkaFin without giving OrkaFin direct database, Sheet, or storage access. It is a design and contract checklist, not authorization to enable a live integration.

## Non-negotiable ownership model

The owning app remains authoritative for its records, identity facts, workspace/record/field permissions, business validation, write execution, receipts, and retention obligations. OrkaFin may persist only its own minimized conversations, recommendations, events, action state, and audits. It must not gain a database connection, ORM model, Google Sheet client, table replica, or raw-record export from the owning app.

The integration seam is the versioned general adapter contract documented in [ORKA_APP_ADAPTER_CONTRACT.md](ORKA_APP_ADAPTER_CONTRACT.md). The Local V1 mock OrkaATS adapter is an example of this seam, not a production transport.

## Onboarding sequence

1. **Define the boundary.** Name the owning app, supported workspaces/pages/entities, protected fields, and explicit non-goals. Confirm that the app can independently enforce record and field visibility.
2. **Add a versioned adapter.** Implement the general `ApplicationAdapter` capabilities through an injected adapter/transport. Register it by app ID in the composition root. Do not add app-specific conditionals to assistant, retrieval, recommendation, or action services.
3. **Write contract tests first.** Run the shared adapter contract scenarios in `tests/contracts/adapter_contract.py` against a fake and then the new adapter. Add app-owned fixtures for success, denial, missing identity, record swap, field redaction, malformed payload, timeout, conflict, and receipt cases. Tests must remain offline unless a reviewed integration environment explicitly changes that rule.
4. **Version deliberately.** Keep the general adapter contract and each transport schema version explicit. Reject unsupported/missing versions and unknown fields. Publish compatible changes additively; create a migration plan and contract-test matrix before a breaking version.
5. **Connect server-side identity.** The browser supplies no identity, role, email, permission, workspace, or action assertion. The deployed server/session layer supplies an authenticated subject reference; the owning adapter resolves and verifies it per request. Define issuer, audience, expiry, nonce/replay, deployment, and key-rotation rules before real traffic.
6. **Recheck authorization at each boundary.** Resolve app/page access, workspace, selected record, visible fields, available features, and available actions from the owning app. Treat all browser navigation as an untrusted hint. Re-resolve and revalidate immediately before any execution.
7. **Create reviewed source catalogs.** Add version-controlled app/page/feature/help/action catalog entries with owner, revision, status, provenance, permissions, and verification status. Knowledge provides retrieval evidence; it never grants permission or replaces the owning app's business rules.
8. **Keep actions closed and receipt-backed.** Start with no executable action. For each approved action, define exact schema, preview, confirmation binding/TTL, idempotency, conflict behavior, owning-app validation, typed failures, and signed or otherwise authenticated receipt semantics. The adapter must execute the write and return the only success authority.
9. **Integrate audits.** OrkaFin records minimized correlation/audit facts for decisions and lifecycle state. The owning app records its own authoritative action/audit event. Link them through request/correlation/idempotency references without copying raw records, secrets, token values, hidden fields, or full payloads.
10. **Pass human gates.** Security, privacy, product, and platform owners approve the transport, identity protocol, field matrix, source catalog, actions, monitoring, retention, and incident plan before any live data is enabled.

## Required adapter behaviors

| Capability | Owning-app responsibility | OrkaFin use |
|---|---|---|
| App/page metadata | Return known public page facts and supported version | Resolve navigation, never infer unknown pages |
| Current identity | Verify a server-side subject and return a bounded identity | Fail closed when missing/unverified; public context omits email |
| Permissions and actions | Return app/page/workspace/record/field/action facts for that identity | Filter retrieval and candidate view; never accept browser claims |
| Selected-record summary/search | Apply record/field checks and return an allowlisted minimized summary | Use only permitted fields; never persist raw records/notes |
| Recent meaningful events | Return allowed, minimized event facts only | Drive deterministic recommendations, not surveillance |
| Action execution | Revalidate, execute once with idempotency, and return a matching receipt | Report success only from that receipt; ambiguous outcomes remain unknown |

The app must make private, archived, missing, and denied records indistinguishable where enumeration risk requires it. The adapter must bound response size and reject malformed/unrecognized data before it reaches provider or persistence boundaries.

## Contract and versioning checklist

- Use the typed contract models and `AdapterCapability` values rather than raw application dictionaries.
- Include request ID, app ID, adapter response ID, timestamps, and schema/contract versions in every adapter response.
- Enforce `extra="forbid"` equivalent behavior on incoming wire payloads and validate UTC timestamps, ID formats, bounded strings, and list sizes.
- Maintain compatibility tests for current and previous supported wire versions. An unknown version is a safe failure, never a best-effort parse.
- Map timeouts, unavailable transport, conflict, validation failure, authorization failure, and malformed response to typed adapter errors with safe messages.
- Preserve the no-live-network test rule through injected transports; a live test needs its own reviewed fixture account and teardown plan.

## Identity, permission, and data checklist

- Bind an authenticated server-side principal to the request; no client claim is a fallback authority.
- Verify app/page/workspace/record/field/action facts together, then bind them to the response lifetime.
- Keep email, raw notes, hidden-field names/values, authorization tokens, and full adapter payloads out of browser responses, provider input, retained messages, events, logs, and audit details.
- Test field-level redaction separately from record denial, and test permission revocation between action proposal and execution.
- Keep candidate/business validation and all writes inside the owning app. OrkaFin has no compensating write route against another app's storage.

## Source catalogs and action receipts

Source catalogs live in reviewed, version-controlled files with stable IDs and provenance. Help content is untrusted data; only approved bounded excerpts and verified structured steps can support output. A provider may improve wording but cannot invent sources, features, actions, permissions, or success.

For an action, require a server-owned proposal containing exact parameter hash, target, action version, verified user/workspace, previewed old value, expiry, and idempotency key. Confirmation is explicit and one-time. At execution, the owning app repeats authorization and business checks and returns a receipt bound to the request, action/version, target, idempotency key, timestamp, and outcome. A timeout or malformed receipt never becomes an asserted no-change/success response.

## Completion evidence

Before an app is marked ready even for a controlled test, provide:

- adapter contract and application-specific integration test output;
- synthetic fixture matrix covering identity, record/field permission, errors, and action replay/conflict;
- source catalog validation and retrieval/grounding evidence;
- audit/event redaction checks and no-direct-storage-access review;
- approved transport/identity design and threat-model update; and
- an updated migration/onboarding acceptance record naming the human owners.

Adding a future app is an architecture change. Update [DECISIONS.md](DECISIONS.md), the threat/security documents, and create or supersede an ADR before implementation.
