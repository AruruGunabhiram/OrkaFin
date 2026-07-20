# Local V1 Permission Model

**Status:** Prompt 7 fixture policy retained; Prompt 11 context enforcement pending human review
**Scope:** Local identity harness, authorization evaluator/redaction, and Prompt 11 context endpoint

## Boundary and decision rule

OrkaATS remains the final authority for candidate application, page, record,
field, and action access. OrkaFin does not derive those grants from a role and does
not read the OrkaATS Sheet. The local fixture policy simulates the facts a future
trusted adapter may return so application services and security tests can be built
before live integration.

Every decision requires two independent inputs:

1. a verified `UserIdentity` returned by an `IdentityResolver`; and
2. request-scoped `TrustedAuthorizationFacts` from the owning adapter or the
   explicit local fixture harness.

The evaluator intersects those inputs with the requested scope. Missing facts,
unknown permission names, and omitted list entries deny. A role label contributes
no app, page, record, field, permission, or action grant. Browser claims are never
an input to the evaluator. The trusted adapter may always narrow the provisional
fixture matrix; OrkaFin must never broaden it.

## Interfaces

| Interface | Responsibility | Fail-closed behavior |
|---|---|---|
| `IdentityResolver.resolve_identity` | Resolve a server-selected subject without trusting browser claims | Missing/unknown selection returns a claim-free unverified identity |
| `LocalFixtureIdentityResolver` | Synthetic local test harness only | Receives no public identity, role, permission, or action fields; those are rejected by `ClientContextHint` validation |
| `TrustedAuthorizationFacts` | Carry explicit app, page, record, field, permission, and available-action facts | Absent facts deny; app denial cannot carry narrower grants |
| `PermissionEvaluator` | Check app, page, permission, record, field, and action scopes | Every omitted/unknown scope denies; role is never consulted for grants |
| `CandidateSummaryRedactor` | Construct `CandidateSummary` from allowed source fields only | Identity/record denial returns no summary; hidden IDs/values are absent |
| `TrustedContextResolutionService` | Orchestrate adapter identity/context/page/permission/action calls and gate candidate retrieval | Unverified identity returns no context; app/page/record denials are audited before safe errors |
| `TrustedSessionResolver` | Supply an opaque subject from server/session state, separate from the request body | Default resolver supplies no subject; static resolver is test-only |

`fixtures/users.yaml` is deliberately marked
`synthetic_local_identity_test_harness` and
`provisional_human_review_required`. It contains fictional `.invalid` email
addresses and synthetic IDs only. It must not contain passwords, tokens, real
people, production exports, or authoritative OrkaATS assignments.

## Existing permission vocabulary

Prompt 7 preserves the four names already declared in
`knowledge/orka_ats/permissions.yaml`:

| Permission | Local meaning | Grant status |
|---|---|---|
| `candidate.view` | Required in addition to an exact record grant before any candidate summary | Admin, recruiter, limited viewer fixtures |
| `candidate.create` | Provisional catalog grant only; no endpoint is implemented in Prompt 7 | Admin and recruiter fixtures |
| `candidate.notes.view` | Exceptional prerequisite for a bounded notes excerpt; an explicit `notes_excerpt` field grant is also required | No Prompt 7 fixture |
| `candidate.update_start_date` | One prerequisite for the disabled provisional action; availability, record access, confirmation, revalidation, adapter execution, and audit remain separate | Admin permission fixture only; no fixture advertises the action as available |

Knowledge catalog membership is vocabulary, not authorization. For example, the
administrator fixture's `candidate.update_start_date` grant does not make the
action executable because `available_action_ids` is empty and the catalog action
is disabled.

## Provisional fixture users

| Fixture | Role label (non-granting) | Candidate records | Pages | Permission grants | Available actions |
|---|---|---|---|---|---|
| `admin` | `administrator` | `CAND-1001`, `CAND-1002` | All six provisional pages | `candidate.view`, `candidate.create`, `candidate.update_start_date` | None |
| `recruiter` | `recruiter` | Assigned fixture record `CAND-1001` | All six provisional pages | `candidate.view`, `candidate.create` | None |
| `limited_viewer` | `limited_viewer` | Allowed fixture record `CAND-1001` | Dashboard, list, profile, pipeline | `candidate.view` | None |
| `unverified` | None | None | None | None | None |

The record lists are synthetic examples of trusted adapter output, not a policy
that role implies assignment. A future adapter can return fewer records or none
for any identity, including an administrator.

## Provisional candidate field matrix

Candidate ID is returned only after exact record visibility succeeds and binds the
summary to that record. All other fields require an explicit per-record entry:

| Field ID | Admin | Recruiter | Limited viewer | Notes |
|---|---:|---:|---:|---|
| `display_name` | Yes | Yes | Yes | Provisional candidate name |
| `recruitment_stage` | Yes | Yes | Yes | Provisional current stage label |
| `recruiter` | Yes | Yes | Yes | Provisional assigned recruiter display value |
| `email` | Yes | Yes | No | Restricted contact value |
| `start_date` | Yes | Yes | No | Calendar date if supplied by adapter |
| `resume_link` | Yes | Yes | No | Restricted owning-app reference; never fetched directly by OrkaFin |
| `created_at` | Yes | No | No | Admin-only provisional metadata |
| `updated_at` | Yes | No | No | Admin-only provisional metadata |
| `notes_excerpt` | No | No | No | Always omitted by current fixtures; explicit field and permission required |
| Unknown field | No | No | No | Deny by default, including for admin |

The redaction summary reports only visible and redacted counts for ordinary source
fields. It never enumerates hidden field IDs or values. A denied notes payload is
omitted without changing these counts so the output does not reveal whether notes
exist. If explicitly permitted later, the excerpt remains bounded, sensitive,
untrusted, request-scoped, excluded from normal logs, and never persisted.

## Safe decision codes

| Code | Meaning for audit/control flow | Safe message behavior |
|---|---|---|
| `allowed` | All required trusted inputs and exact grants are present | Generic allowed statement |
| `identity_missing` | No identity was resolved | Requests sign-in verification; echoes no claim |
| `identity_unverified` | Resolver could not verify the selected identity | Same generic sign-in message |
| `trusted_facts_missing` | No current adapter/fixture authorization response | Says access could not be verified |
| `app_access_denied` | Identity/app binding or explicit app access failed | Generic area unavailable message |
| `page_access_denied` | Page absent from trusted page grants | Generic area unavailable message |
| `record_access_denied` | Exact record absent from trusted visibility grants | Generic candidate information unavailable message; does not confirm existence |
| `field_access_denied` | Field absent from that record's field allowlist | Same generic candidate message; no field ID/value |
| `action_access_denied` | Action absent from trusted available actions | Generic action unavailable message |
| `permission_missing` | Known permission absent from trusted grants | Generic required-access message; no permission name |
| `permission_unknown` | Requested permission is not in controlled vocabulary | Same generic required-access message |

Decision objects contain only the check scope, boolean result, stable code, and
safe message. Requested IDs, emails, role claims, hidden field names, permission
names, and values are not echoed. Audit services may record the stable code with
their separately bounded references under the audit data policy.

## Prompt 11 endpoint enforcement

The context service constructs `AuthorizationContext` only from the
adapter-verified `UserIdentity` and fresh `TrustedAuthorizationFacts`. It checks
app and page before returning context. For a selected candidate it checks the
exact `SelectedEntityRef` and `candidate.view` before calling
`get_selected_entity_summary`. Browser identity, role, permission, action,
workspace, and request-ID fields are rejected before this service is invoked.
Returned available actions are the conservative intersection of the adapter's
fresh authorization facts and its separate available-actions response.

The selected candidate summary requests the eight established ordinary candidate
fields and never requests notes. The adapter returns only allowed fields; the
limited-viewer fixture therefore returns three visible fields, five redacted
fields, no action, and only `candidate.view`. A browser attempt to add an
administrator role or permission claim receives `422 validation_error`. A
record-swap to the private fixture fails with
`record_access_denied`, creates a minimized `permission_denied` audit, and returns
the safe `candidate_access_denied` API code without confirming the record.

This endpoint does not make the existing role labels granting, enable a catalog
action, or authorize any write.

## Action boundary

An allowed evaluator result is necessary but never sufficient to mutate state.
Prompt 18 adds proposal and confirmation endpoints but no executor. The mock
administrator alone has both `candidate.update_start_date` and current
adapter-advertised availability for the selected visible candidate. Recruiter and
limited-viewer fixtures remain denied. Proposal requires the permission, action
availability, exact candidate grant, and a visible typed `start_date` value.
Acceptance repeats those checks after binding the current verified
user/workspace/target to the issued confirmation.

This is a provisional mock policy for human review, not a role-derived production
grant. Role still creates no permission. Cancellation remains available to the
bound user without requiring continued action permission because it cannot widen
access or execute. Any future execution still requires immediate authoritative
revalidation, owning-adapter execution, receipt validation, and audit logging.

## Human review checkpoint

Prompt 8 must not begin until the designated OrkaATS product owner and security
reviewer decide the following provisional choices:

- whether the three role labels and four synthetic fixture identities are suitable;
- whether page grants for each fixture are correct;
- how real record assignment/workspace/project visibility will be represented
  independently of role (Q-003);
- the authoritative field IDs, whether field names are themselves sensitive, and
  the admin/recruiter/limited-viewer matrix (Q-002);
- whether the Prompt 18 administrator action permission/availability should be
  approved for the mock-only confirmation POC;
- whether notes capability should remain entirely inactive, and what additional
  review would be required before any adapter can supply an excerpt.

| Review field | Value |
|---|---|
| OrkaATS product reviewer | Pending |
| Security reviewer | Pending |
| Review date | Pending |
| Outcome | Pending: approve, approve with recorded conditions, or request changes |
| Conditions/changes | Pending |

Approval validates a local fixture policy and interface handoff only. It does not
approve production authentication, Google OAuth, Workspace identity, live adapter
transport, candidate-note processing, or any state-changing endpoint.
