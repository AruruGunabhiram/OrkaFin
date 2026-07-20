"""Explicit minimization policy for conversation text sent to a provider."""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    LongText,
    ModelDataPolicy,
    PersistencePolicy,
)
from orkafin.domain.privacy import redact_sensitive_text
from orkafin.providers.contracts import (
    PROVIDER_HISTORY_MAX_MESSAGE_CHARACTERS,
    PROVIDER_HISTORY_MAX_MESSAGES,
    PROVIDER_HISTORY_MAX_TOTAL_CHARACTERS,
    HistoryRole,
    SafeHistoryMessage,
)


class HistoryInputRole(StrEnum):
    """Roles an internal history reader may encounter before provider minimization."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    DEVELOPER = "developer"


class HistorySensitivity(StrEnum):
    """Trusted server classification; clients cannot set this as authority."""

    PROVIDER_SAFE = "provider_safe"
    SENSITIVE = "sensitive"


class ConversationHistoryEntry(DomainModel):
    """Internal history input carrying server-owned visibility metadata."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    role: HistoryInputRole
    content: LongText
    sensitivity: HistorySensitivity = HistorySensitivity.PROVIDER_SAFE


class BoundedConversationHistoryPolicy:
    """Keep only recent, user-visible, explicitly provider-safe conversation text."""

    max_messages: ClassVar[int] = PROVIDER_HISTORY_MAX_MESSAGES
    max_message_characters: ClassVar[int] = PROVIDER_HISTORY_MAX_MESSAGE_CHARACTERS
    max_total_characters: ClassVar[int] = PROVIDER_HISTORY_MAX_TOTAL_CHARACTERS

    def minimize(
        self, entries: tuple[ConversationHistoryEntry, ...]
    ) -> tuple[SafeHistoryMessage, ...]:
        """Drop hidden/sensitive entries and truncate the newest eligible messages."""
        remaining = self.max_total_characters
        selected: list[SafeHistoryMessage] = []
        visible_roles = {
            HistoryInputRole.USER: HistoryRole.USER,
            HistoryInputRole.ASSISTANT: HistoryRole.ASSISTANT,
        }
        for entry in reversed(entries):
            role = visible_roles.get(entry.role)
            if role is None or entry.sensitivity is HistorySensitivity.SENSITIVE:
                continue
            if remaining <= 0 or len(selected) >= self.max_messages:
                break
            content = redact_sensitive_text(entry.content)[
                : min(self.max_message_characters, remaining)
            ].strip()
            if not content:
                continue
            selected.append(SafeHistoryMessage(role=role, content=content))
            remaining -= len(content)
        return tuple(reversed(selected))
