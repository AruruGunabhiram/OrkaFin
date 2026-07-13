# ADR-003: No Vector Database for Initial V1

- **Status:** Proposed — pending Prompt 1 human approval
- **Date:** 2026-07-13
- **Decision owners:** OrkaFin engineering and product knowledge owners
- **Scope:** Retrieval over approved OrkaATS knowledge

## Context

The initial corpus is expected to be a small, version-controlled set of OrkaATS
feature, page, help, permission, and action catalogs. V1 needs source provenance,
version/status checks, permission filtering, deterministic tests, and honest
unknown behavior more than approximate semantic search infrastructure. There is no
labelled retrieval evaluation showing that embeddings solve a current failure.

A vector database would add chunking, embedding model/version, re-indexing,
deletion, permission filtering, data handling, dependency, and operational choices
before the team knows the corpus or query failures.

## Decision

Use deterministic structured retrieval for initial V1. Knowledge entries have
strict schemas and stable IDs with app, page/route, feature, status, roles/
permissions, version/revision, owner, updated date, keywords, instructions, and
safe source references as applicable.

Retrieval performs hard filters for active status, app/schema compatibility,
verified permission and page/context before deterministic text/keyword ranking.
Results expose source IDs and revisions. Missing or ambiguous grounded evidence
returns unavailable rather than provider-memory speculation.

Do not add embeddings, a vector index/database, semantic reranker, or hidden
unstructured ingestion to Local V1. Deterministic metadata filtering remains a
security boundary even if semantic ranking is later added.

## Security and content boundaries

Approved knowledge text is still untrusted as instruction. It cannot set
permissions, create action definitions, change system rules, or attest success.
Candidate notes are not part of the knowledge corpus and are excluded from model
input by default. Retrieval operates only on content allowed for the resolved user
and context.

The action catalog is explicit and separate from help prose. A help article that
mentions an operation does not make it executable.

## Consequences

Positive consequences:

- Repeatable ranking and exact expected-source tests.
- Transparent source/version debugging and easy version-control review.
- Lower local setup, data handling, and operational complexity.
- Permission filters occur before content is exposed to a provider.

Costs and limitations:

- Synonyms and natural-language variation need curated keywords/aliases.
- Recall may decline as the corpus grows or documents become less structured.
- Knowledge authors must maintain metadata and validation.
- The decision does not claim vectors are never useful; it requires evidence.

## Alternatives considered

**Vector database immediately:** rejected because there is no measured retrieval
gap or scale need, while permission/provenance complexity is immediate.

**External web/document search:** rejected for V1 because it weakens approval,
version, privacy, and reproducibility boundaries.

**Let the model answer from general knowledge:** rejected because it can invent
Orka features and cannot prove source revision or permission.

**Simple full-text search without schemas:** smaller initially but lacks the hard
metadata, ownership, permission, and version constraints required for grounding.
Rejected as the sole approach.

## Measurement plan and verification

- Validate every catalog schema, ID/reference, owner, status, revision, and
  permission name before startup/test.
- Maintain a labelled set of representative, synonym, ambiguous, forbidden,
  outdated, and no-answer questions.
- Measure top-k source precision/recall or an agreed equivalent, no-answer accuracy,
  permission leakage, deterministic repeatability, and latency.
- Test document prompt injection, disabled entries, duplicate IDs, broken
  references, unknown features/actions, and cross-role source visibility.
- Return cited source IDs/revisions and ensure the provider cannot introduce an
  uncatalogued source.

No threshold is invented here. Prompt 14 must publish the actual evaluation set,
baseline, and human-approved success criteria.

## Change triggers

Reconsider only when a versioned labelled evaluation shows material repeated
misses after schema, aliases, keyword ranking, and authoring quality are improved,
or when measured corpus size/latency makes the deterministic implementation
inadequate.

A superseding ADR must compare at least the deterministic baseline and proposed
hybrid/semantic approach, including permission filtering before disclosure,
provenance, tenant separation, embedding provider/data retention, index versioning,
update/deletion latency, failure fallback, cost, operations, and rollback. It must
not remove deterministic security filters.

