"""Immutable code-owned prompt template metadata."""

from __future__ import annotations

from dataclasses import dataclass

from orkafin.providers.contracts import ResponseIntent


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """One versioned developer template for a server-selected response intent."""

    template_id: str
    version: str
    intent: ResponseIntent
    developer_instruction: str
