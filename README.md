# OrkaFin Local V1

OrkaFin Local V1 is a permission-aware guidance and recommendation layer for one
pilot application, OrkaATS. It is not a generic chatbot and it is not the system
of record for candidates. OrkaATS owns candidate data, candidate permissions,
business validation, and every candidate write.

The current repository includes the typed local service scaffold, Prompt 3's safe
configuration/error/correlation foundation, and Prompt 4's canonical versioned
domain contracts. It includes an application factory and a versioned
`GET /health` endpoint, but no database schema, business endpoint, knowledge
loader, adapter implementation, widget, or model-provider integration.

## Local quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
make lint typecheck test
make run
```

Then request `http://127.0.0.1:8000/health`. See
[local setup](docs/LOCAL_SETUP.md) for all quality, migration, and knowledge
validation commands.

## V1 decisions at a glance

- Run one modular local FastAPI service on Python 3.11 or newer.
- Use Pydantic v2 contracts, SQLAlchemy 2, SQLite, and Alembic when implementation
  begins. Candidate records must never be added to OrkaFin persistence.
- Integrate Orka applications only through a versioned, application-neutral
  adapter contract. OrkaFin must never read or write the OrkaATS Google Sheet
  directly.
- Treat browser-supplied identity, email, role, permissions, selected record, and
  available actions as untrusted hints.
- Use structured deterministic retrieval and a deterministic response provider by
  default. An external model is optional and is never an authorization or action
  authority.
- Deliver grounded guidance and recommendations. Prompt 18 implements one
  mock-only action through confirmation, with execution disabled pending a
  separate human checkpoint and remaining safety gates.
- Use explicit mock identities locally. A mock identity is not production
  authentication and proves nothing about a live Apps Script deployment.

## Documentation map

The local V1 source-of-truth documents are:

- [V1 scope and non-goals](docs/V1_SCOPE_AND_NON_GOALS.md)
- [Architecture and request flows](docs/ARCHITECTURE.md)
- [Security model](docs/SECURITY_MODEL.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Decisions, assumptions, and open questions](docs/DECISIONS.md)
- [Future migration plan](docs/FUTURE_MIGRATION_PLAN.md)
- [Domain model and ownership contracts](docs/DOMAIN_MODEL.md)
- [Event, action, and audit persistence model](docs/EVENT_AND_AUDIT_MODEL.md)
- [Action proposal and confirmation review](docs/ACTION_AND_CONFIRMATION_FLOW.md)
- [ADR-001: local-first architecture](docs/adr/ADR-001-local-first-architecture.md)
- [ADR-002: application data ownership](docs/adr/ADR-002-application-data-ownership.md)
- [ADR-003: no vector database for initial V1](docs/adr/ADR-003-no-vector-database-for-initial-v1.md)
- [ADR-004: provider-independent AI interface](docs/adr/ADR-004-provider-independent-ai-interface.md)

The [ecosystem context](docs/source/ORKAFIN_ECOSYSTEM_CONTEXT.md) describes the
longer-term Orka OS direction. The
[implementation prompt pack](docs/plans/OrkaFin_Local_V1_Implementation_Prompt_Pack.md)
controls build sequencing. If broad future context conflicts with the approved
local V1 documents, the narrower local V1 decision and its ADR govern V1.

## Repository boundary

The `orkafin` import package uses a `src` layout with modules for API, core
configuration, domain contracts, application services, adapters, infrastructure,
knowledge, providers, and the framework-free web widget. These are modules in one
deployable service, not microservices.

The planned database may contain OrkaFin-owned conversations, messages, events,
recommendations, feedback, action state, execution receipts, and audit records.
It must not contain a `candidates` table, a replica of candidate rows, or raw
candidate notes. A mock OrkaATS adapter may keep isolated fixture state outside
the OrkaFin persistence model.

## Verification for this increment

Prompt 1 is complete only when all required documents exist, relative links
resolve, required boundary language is present, and a human approves the
architecture. The repository currently has no configured Markdown link checker;
Prompt 1 therefore uses explicit path/link validation plus manual substantive
review. Verification commands and results belong in the Prompt 1 handoff.

## Change triggers for a frozen decision

Do not silently change a boundary. A change requires an update to
`docs/DECISIONS.md`, the affected architecture/security documents, and a new or
superseding ADR. Re-review is mandatory if a change would add production identity,
direct Sheet access, candidate persistence, an autonomous action, a vector
database, a multi-service deployment, or reliance on an external model.
