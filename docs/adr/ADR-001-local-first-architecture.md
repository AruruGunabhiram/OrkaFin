# ADR-001: Local-First Modular Architecture

- **Status:** Proposed — pending Prompt 1 human approval
- **Date:** 2026-07-13
- **Decision owners:** OrkaFin engineering and product
- **Scope:** Local V1 topology and baseline technology

## Context

OrkaFin needs a production-minded local pilot around OrkaATS, but it has not yet
validated product usefulness, live identity, adapter transport, scale, or an
action. Splitting an unproven workflow across services would add network failure,
deployment, schema coordination, and observability work without improving the
ownership boundary. Conversely, a loose prototype without types, migrations, or
module boundaries would harden shortcuts into the design.

Apps Script remains part of the wider ecosystem, but server-side Apps Script runs
on Google infrastructure and cannot be assumed to call a service on a developer's
`localhost`. Local V1 must not pretend that mock connectivity proves a production
integration.

## Decision

Build Local V1 as one modular FastAPI service using:

- Python 3.11 or newer, targeting Python 3.11 semantics;
- package name `orkafin` in a `src` layout;
- Pydantic v2 for strict versioned contracts;
- SQLAlchemy 2 and SQLite for OrkaFin-owned local persistence;
- Alembic for every persistent schema change;
- pytest, Ruff, and mypy as required quality gates;
- a framework-free HTML/CSS/JavaScript widget;
- explicit internal application, adapter, provider, repository, and knowledge
  interfaces with dependency injection.

Modules are code ownership/dependency boundaries inside one process, not
microservices. The service starts and completes its deterministic demo without
external secrets or network services.

## Boundaries

Local V1 does not add AWS/GCP production deployment, Cloud Run, Kubernetes, Kafka,
Pub/Sub, Redis, a service mesh, worker cluster, vector database, LangChain,
LangGraph, or a multi-agent framework. It does not implement live Apps Script
identity or connectivity.

This ADR does not permit the modular service to own candidate records or bypass an
Orka application. That boundary is defined in
[ADR-002](ADR-002-application-data-ownership.md).

## Consequences

Positive consequences:

- One repeatable local setup and transaction boundary.
- Straightforward debugging, migrations, request correlation, and test fixtures.
- Interfaces can be exercised as ordinary typed Python rather than remote mocks.
- The later hosting or storage implementation can change behind explicit seams.

Costs and limitations:

- SQLite and one process do not claim multi-user production concurrency, tenant
  isolation, high availability, or tamper-evident audit storage.
- In-process boundaries rely on dependency tests and review rather than network
  enforcement.
- A later remote deployment needs authentication, secrets, observability,
  backups, retention, and operational ownership that local V1 does not supply.

## Alternatives considered

**Apps Script-only OrkaFin:** aligns with the current UI ecosystem but would couple
central orchestration to Apps Script runtime/storage limits and still not solve a
general adapter boundary. Rejected for Local V1 backend design.

**Microservices from the start:** might isolate components eventually, but no
measured scale, team ownership, or independent availability need exists. Rejected.

**No database/migrations:** simpler for a throwaway demo, but conversations,
events, feedback, action state, and audits need explicit evolution boundaries.
Rejected.

**Frontend framework:** unnecessary for the compact embeddable widget and adds a
build/runtime dependency before UX complexity warrants it. Rejected for V1.

## Verification

- Prompt 2 creates only one application factory/deployable service and a `src`
  package; no separate network services.
- The quality gates run with Python 3.11-compatible configuration.
- The app and full deterministic demo run without external secrets/network.
- Repository/dependency review finds none of the excluded infrastructure or
  frameworks.
- SQLite migrations include only OrkaFin-owned data and upgrade from an empty
  database reproducibly.
- Documentation states that mock identity/connectivity is not production proof.

## Change triggers

Reconsider through a superseding ADR only with evidence of independent scaling or
availability needs, sustained concurrency/database contention, a long-running
workload unsuitable for requests, distinct operational ownership, remote multi-user
requirements, or a live integration need. The new ADR must include measurements,
security boundaries, failure/transaction semantics, operational cost, local
developer workflow, migration, and rollback.

