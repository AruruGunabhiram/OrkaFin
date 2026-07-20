# V1 Scope and Non-Goals

**Status:** Frozen for Prompt 1 human review  
**Pilot:** OrkaATS  
**Deployment:** Local development and local demonstration only

## Product outcome

Local V1 proves that OrkaFin can provide useful, grounded, permission-aware help
inside the context of OrkaATS without taking ownership of candidates or trusting
the browser as an authority. The complete mandatory V1 must run and be testable
without an external AI service.

The primary user is an internal OrkaATS pilot user represented locally by an
explicit fixture identity. The fixture will eventually include roles such as
recruiter, limited viewer, and administrator, but role-to-field policy is not
approved in Prompt 1.

## Mandatory V1 capabilities

The ordered implementation prompts may deliver:

1. A single modular FastAPI backend and framework-free HTML/CSS/JavaScript widget.
2. Versioned domain contracts that keep client claims distinct from
   adapter-verified identity, context, permissions, and fields.
3. A mock OrkaATS adapter with synthetic candidate fixture state isolated from
   OrkaFin persistence.
4. Grounded answers from version-controlled OrkaATS feature, page, and help
   catalogs using deterministic structured retrieval.
5. A deterministic response provider that supports all tests and the local demo;
   an optional external provider may improve wording only.
6. Conversation history, meaningful events, recommendations, feedback, and
   appropriate audit records stored as OrkaFin-owned data.
7. Deny-by-default authorization and field-level candidate summary redaction based
   on facts returned by a trusted adapter boundary.
8. Honest failures and source-aware responses that do not invent features,
   permissions, records, or successful writes.
9. Security, adversarial, and end-to-end tests for the local boundary.

Guidance questions are limited to approved knowledge and permitted current
context. Representative questions include:

- What does this OrkaATS page do?
- What can I do on this page?
- What is the documented next step in this workflow?
- How do I use an approved OrkaATS feature?
- Which fields can I see for the selected candidate?
- Summarize the permitted fields in this candidate context.
- What does this approved pipeline stage mean?
- Which existing feature may help with the current task?
- What permitted action is available here?
- Why is a requested fact or operation unavailable?

An answer is unavailable when approved knowledge, verified context, or permission
is missing. The system must say so rather than guess.

## Optional confirmed-action proof of concept

Prompt 18 opts into preparation and confirmation for exactly one low-risk mock
action, `candidate.update_start_date`. The action catalog, permission/current-value
checks, exact preview, one-time challenge, expiry, replay protection, state, audit,
API, and widget controls are implemented. This approval does not include execution.

Even in mock mode, execution remains forbidden until the catalog, permission check,
record visibility, typed validation, exact preview, one-time expiring
confirmation, parameter binding, execution-time revalidation, idempotency, audit
trail, adapter failure handling, and receipt validation are implemented and
reviewed. Prompt 18 stops at `confirmed`/`accepted` with
`execution_enabled=false`; no execution row or adapter write occurs. No autonomous,
batched, destructive, background, or live Sheet action is part of V1.

## Data boundary

OrkaFin may persist only OrkaFin-owned operational data necessary for the local
assistant: conversations, messages, request correlations, approved knowledge
references, meaningful events, recommendations, feedback, action proposal state,
hashed confirmation state, adapter receipts, and audit records. Retention periods
remain an open policy decision.

OrkaATS owns and remains authoritative for:

- candidate records and identifiers;
- candidate notes, private fields, and attachments;
- recruiting stages and allowed stage transitions;
- user, record, field, and action permissions affecting candidates;
- candidate validation and writes;
- the Google Sheet or other operational store behind OrkaATS.

OrkaFin persistence must not contain a candidate table, candidate-row replica,
raw candidate notes, hidden fields, Sheet credentials, or unrestricted snapshots.
A short-lived, redacted `CandidateSummary` returned by an adapter is context, not
an OrkaFin-owned candidate record.

## Explicit non-goals

Local V1 does not include:

- production deployment, production authentication, or a claim that Google
  Workspace identity has been integrated;
- AWS, GCP production infrastructure, Cloud Run deployment, Kubernetes,
  microservices, Kafka, Pub/Sub, Redis, or background job infrastructure;
- direct access from OrkaFin to an OrkaATS Sheet, Apps Script storage, or Drive;
- multiple Orka app integrations or cross-app action workflows;
- a vector database, embeddings dependency, unstructured semantic index, or a
  claim that deterministic retrieval will fit every future corpus;
- LangChain, LangGraph, a multi-agent framework, generic tool execution, or
  autonomous planning;
- continuous training or automatic model retraining from user behavior;
- raw candidate notes in model input by default, secrets in frontend code, or full
  request/model payloads in logs;
- voice input, rich production analytics, production observability, high
  availability, or scale claims;
- a live Apps Script-to-localhost integration demonstration;
- application functionality during Prompt 1.

## Quality and acceptance boundary

Every later increment must add tests and preserve these decisions. Mandatory V1
acceptance requires deterministic end-to-end operation with no external API key,
permission-leakage tests, grounded-source behavior, adapter failure behavior, and
documentation of residual risk. The optional action is not required for mandatory
V1 acceptance.

## Verification steps

Reviewers should verify that:

1. Searches for `candidate` in future migrations reveal no OrkaFin candidate
   table.
2. Adapter tests prove the browser cannot elevate role, permission, record access,
   or available actions.
3. The local demo starts and completes in deterministic mode without a provider
   key.
4. Grounding tests reject unknown features and unauthorized or hidden fields.
5. No action can execute on a chat message or on browser-provided permission
   claims.
6. Source and architecture documents continue to state the OrkaATS ownership and
   direct-Sheet prohibition consistently.

## Change triggers

Revisit scope through a reviewed ADR when the pilot adds another Orka app, moves
outside a local machine, connects to live Apps Script, needs production identity,
adds a second executable action, measures insufficient structured retrieval, or
proposes storing new application-owned data. Product convenience alone does not
override the ownership or authorization boundary.
