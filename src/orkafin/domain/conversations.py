"""OrkaFin-owned conversation and bounded message contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import Field, StringConstraints, model_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    HandlingRule,
    Identifier,
    ModelDataPolicy,
    PersistencePolicy,
    SensitiveFieldPolicy,
    ShortText,
    UtcDatetime,
)
from orkafin.domain.context import WorkspaceRef
from orkafin.domain.identifiers import RequestId

MessageText = Annotated[
    str,
    StringConstraints(min_length=1, max_length=8_000, strip_whitespace=True, strict=True),
]


class ConversationStatus(StrEnum):
    """Conversation lifecycle managed by OrkaFin."""

    ACTIVE = "active"
    CLOSED = "closed"


class Conversation(DomainModel):
    """Conversation ownership envelope, not unrestricted model memory."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="title",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE,),
            ),
        ),
    )

    conversation_id: Identifier
    owner_user_id: Identifier
    workspace: WorkspaceRef
    title: ShortText | None = None
    status: ConversationStatus
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def validate_timestamps(self) -> Conversation:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


class MessageRole(StrEnum):
    """Persistable message roles; hidden system/developer prompts are intentionally absent."""

    USER = "user"
    ASSISTANT = "assistant"


class Message(DomainModel):
    """Bounded user-visible message with minimized source references."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
        sensitive_fields=(
            SensitiveFieldPolicy(
                field_name="content",
                classification=DataClassification.CONFIDENTIAL,
                rules=(HandlingRule.MINIMIZE, HandlingRule.REDACT_FROM_LOGS),
            ),
        ),
    )

    message_id: Identifier
    conversation_id: Identifier
    role: MessageRole
    content: MessageText
    source_ids: tuple[Identifier, ...] = Field(default=(), max_length=20)
    request_id: RequestId
    created_at: UtcDatetime
