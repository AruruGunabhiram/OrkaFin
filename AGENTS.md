# OrkaFin Repository Instructions

## Product boundaries

- OrkaFin is the permission-aware intelligence and agent layer for Orka OS.
- OrkaFin is not a generic chatbot.
- OrkaATS owns candidate data, permissions, business rules, and writes.
- OrkaFin must never directly read or write the OrkaATS Google Sheet.
- Browser-provided identity, email, role, permissions, and available actions are untrusted.
- State-changing actions require permission revalidation, confirmation, adapter execution, and audit logging.
- Never fabricate a feature, permission result, retrieved source, action result, or successful write.

## Local V1 architecture

- Use Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, Alembic, pytest, Ruff, and mypy.
- Build one modular service, not microservices.
- Do not introduce LangChain, LangGraph, Redis, a vector database, Kubernetes, Kafka, or cloud deployment in V1.
- Structured deterministic retrieval is the default.
- Automated tests and the local demo must work without an external AI provider.
- Keep the assistant widget framework-free unless an approved decision changes this.

## Working rules

- Inspect existing files and git status before modifying anything.
- Implement only the current prompt from the implementation pack.
- Do not silently replace interfaces created by earlier prompts.
- Preserve working functionality unless there is a documented reason to change it.
- Add or update tests with every implementation increment.
- Run the required lint, type-check, migration, and test commands.
- Do not claim completion when required checks fail.
- Update architecture documentation when an approved boundary changes.
- Stop at human-review checkpoints before continuing.
- Summarize files changed, commands run, assumptions, failures, and unresolved risks.
