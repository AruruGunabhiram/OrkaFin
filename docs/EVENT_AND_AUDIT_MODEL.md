# OrkaFin Event, Action, and Audit Persistence

## Scope and ownership

The local SQLite database retains only OrkaFin-owned operational state. It is not
an OrkaATS data store and contains no `candidates` table, candidate-row mirror,
candidate notes, attachments, raw browser context, credentials, tokens, API keys,
or raw model prompts. OrkaATS remains the authority for candidate records,
visibility, business policy, and writes.

The database URL is `sqlite:///./var/orkafin.db` by default and can be overridden
only with the validated `ORKAFIN_DATABASE_URL` SQLite setting. Initialize it with
`make database-init` (or `python scripts/init_database.py`); both run Alembic to
the current revision.

## Tables

| Table | OrkaFin purpose | Important safeguards |
|---|---|---|
| `conversations` | Minimized user conversation envelope | Versioned, workspace-scoped, status constrained |
| `messages` | User-visible bounded messages | User/assistant roles only; no hidden prompt role |
| `user_events` | Allowlisted meaningful events | Scalar validated metadata only; no keystrokes |
| `recommendations` | Rule-derived guidance state | Kind/status constrained and source IDs bounded by domain validation |
| `recommendation_impressions` | Shown-recommendation measurement | FK to a recommendation; no candidate payload |
| `recommendation_feedback` | Bounded feedback | FK to a recommendation and constrained feedback type |
| `action_proposals` | Prepared, unexecuted action intent | Typed parameter JSON, parameter hash, and unique idempotency key |
| `action_confirmations` | Hash-only confirmation state | Stores only the confirmation-secret hash, never plaintext |
| `action_executions` | Receipt-backed execution outcome | Unique idempotency key and validated receipt JSON when present |
| `audit_records` | Security-relevant facts | Append-only API plus SQLite update/delete-blocking triggers |

All timestamp values are supplied by UTC-validated domain objects. Schema-version
columns preserve the accepted domain contract version on records that are expected
to evolve. SQLAlchemy models use foreign keys, indexes, enumerated check
constraints, and SQLite foreign-key enforcement on every application connection.

## Candidate references only

Candidate identifiers are not business records in this database. They may occur
only as an application/entity reference, with no copied name, stage, note, field,
or visibility data.

| Location | Candidate-reference fields | Why it is permitted |
|---|---|---|
| `user_events` | `entity_app_id`, `entity_type`, `entity_id` | Correlates a meaningful user event to the requested application entity |
| `action_proposals` | `target_app_id`, `target_entity_type`, `target_entity_id` | Binds a proposal to the adapter-revalidated target |
| `action_executions` | `target_app_id`, `target_entity_type`, `target_entity_id` | Links a receipt-backed outcome to the target |
| `audit_records` | `target_app_id`, `target_entity_type`, `target_entity_id` | Records a minimized security-relevant target reference |

No other table contains candidate references. These columns are bounded identifiers
and do not grant access or replace live OrkaATS permission checks.

## Serialization boundary

Repositories accept strict Prompt 4 domain objects, not HTTP request bodies or
arbitrary dictionaries. The explicit serializers select only approved fields and
use Pydantic JSON serialization solely for bounded `BoundedMetadata`, typed action
parameters, previews, and adapter receipts. This excludes browser claims,
candidate summaries and notes, raw model prompts, secrets, credentials, tokens,
and unknown JSON keys before persistence is reached.

## Prompt 11 context audit integration

The context service uses the existing append-only `audit_records` table; no schema
or Alembic revision changed. `DatabaseAuditRecorder` owns a short transaction for
each record so a sensitive read is committed before candidate data is returned and
a denial is committed before its safe error is raised.

| Event | Outcome | Minimized details |
|---|---|---|
| `candidate_read` | `allowed` | Visible/redacted counts, redaction boolean, `application_adapter` source label |
| `permission_denied` | `denied` | Check scope and stable authorization decision code |
| `identity_denied` | `denied` | Stable `identity_unverified` code; no actor or target |

The separate bounded target reference may identify the selected candidate for
security review. Details never store visible or hidden field IDs/values, browser
claims, raw candidate notes, or unrestricted adapter responses. These records are
not written to routine logs and remain unavailable through public APIs.

## Retention assumptions

No retention duration is approved yet (Q-008 and Q-012). For the local pilot:

- the operator owns the local `var/orkafin.db` file and removes it when resetting
  synthetic demo data;
- tests use temporary SQLite files and remove them after each test;
- audit rows remain append-only for the life of a local database and are deleted
  only by deleting the entire local pilot database under operator review;
- no production retention, deletion, backup, or restore claim is made.

Before a non-local deployment, product, privacy, and security owners must approve
record-specific retention, deletion, backup, restore, access review, and incident
handling policies.

## Prompt 6 handoff

- Database URL: `sqlite:///./var/orkafin.db` (override: `ORKAFIN_DATABASE_URL`).
- Initial Alembic revision: `36475e375cb5`.
- Repository interface: `OrkaFinRepository(session)` with `add_*` methods for
  validated records, `append_user_event`, `append_audit_record`,
  `get_conversation`, `update_conversation`, and `list_messages`.
- Idempotency: `action_proposals.idempotency_key` and
  `action_executions.idempotency_key` are independent unique, bounded keys. A
  later execution workflow must resolve/reuse the proposal key before adapter
  work and reject duplicate execution keys rather than run a second write.

## Prompt 17 meaningful events and recommendation feedback

`POST /api/v1/events` accepts only browser-originated `app_opened`,
`page_viewed`, and `candidate_selected` events. OrkaFin itself records
`assistant_query_submitted`, recommendation impressions/outcomes, feedback, and
future action lifecycle events. The complete validated event vocabulary is:

`app_opened`, `page_viewed`, `candidate_selected`, `assistant_query_submitted`,
`recommendation_shown`, `recommendation_accepted`,
`recommendation_dismissed`, `feedback_submitted`, `action_proposed`,
`action_confirmed`, `action_succeeded`, and `action_failed`.

Events bind actor, workspace, app, and any candidate reference to freshly
resolved context; callers cannot supply these fields. Metadata is a maximum of
16 scalar entries / 2 KiB. It rejects sensitive key names and email-like values,
so events never retain full assistant questions, candidate notes, email,
credentials, tokens, prompts, hidden fields, or keystrokes.

Recommendation feedback is submitted to `POST /api/v1/feedback` with a
recommendation ID, `helpful`, `not_helpful`, `accepted`, or `dismissed`, current
context hint, optional bounded comment, and optional preference (`enabled`,
`reduced`, or `disabled`). The service validates that the recommendation belongs
to the resolved user/workspace before storing it. Preferences live in the
OrkaFin-only `recommendation_preferences` table; they do not modify OrkaATS.
The `9c2e4f6a1b73` migration adds that table and source-reference storage for
recommendations.

## Prompt 18–19 action and execution audits

The migration `e7a1c4b92d10` adds `action_permission_checked` to the audit
vocabulary and enforces one confirmation row and one confirmation-secret digest
per proposal. It recreates the SQLite append-only update/delete triggers after the
audit check constraint changes.

The confirmation-only workflow appends `action_permission_checked`,
`action_proposed`, `action_confirmation_issued`, `action_confirmed`,
`action_confirmation_rejected`, `action_confirmation_expired`, and
`action_tampering_rejected` as applicable. Details contain only bounded IDs,
phase/status, TTL, and safe reason/decision codes. Old/new values, raw requests,
plaintext challenges, parameter hashes, token hashes, hidden fields, and exception
text are excluded. There is still no audit-read endpoint.

The Prompt 19 migration `c19e2a4b7d01` enforces one execution row per proposal and
adds `action_adapter_requested` and `action_final_result` to the append-only audit
vocabulary. Execution appends `action_execution_attempted`, a fresh
`action_permission_checked`, `action_adapter_requested` only after reservation,
one of `action_execution_succeeded|failed|unknown`, and `action_final_result`.
Replays never append a second adapter-request or outcome event. The exact records
and outcomes are reviewed in
[`ACTION_AND_CONFIRMATION_FLOW.md`](ACTION_AND_CONFIRMATION_FLOW.md).
