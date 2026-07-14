"""Public contracts for deterministic, source-aware knowledge retrieval."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import ClassVar

from pydantic import Field, field_validator, model_validator

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    LowercaseIdentifier,
    ModelDataPolicy,
    PersistencePolicy,
    ShortText,
)
from orkafin.domain.context import ResolvedPageContext
from orkafin.domain.identifiers import Permission
from orkafin.domain.sources import RetrievedSource

_QUESTION_WORDS = re.compile(r"[^a-z0-9]+")


def normalize_question(value: str) -> str:
    """Return the bounded canonical query form used by the retrieval index."""
    return " ".join(_QUESTION_WORDS.sub(" ", value.lower()).split())


class RetrievalIntent(StrEnum):
    """Deterministic guidance labels passed to a later response provider."""

    EXPLAIN_THIS_PAGE = "explain_this_page"
    WHAT_CAN_I_DO_HERE = "what_can_i_do_here"
    FEATURE_QUESTION = "feature_question"
    STEP_BY_STEP_HELP = "step_by_step_help"
    UNKNOWN_FEATURE = "unknown_feature"


class RetrievalRequest(DomainModel):
    """Trusted retrieval inputs; this model intentionally contains no entity content."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.RESTRICTED,
        persistence=PersistencePolicy.REQUEST_SCOPED_ONLY,
    )

    normalized_question: ShortText
    context: ResolvedPageContext
    trusted_permissions: tuple[Permission, ...] = Field(max_length=100)
    selected_entity_type: LowercaseIdentifier | None = None
    limit: int = Field(default=5, ge=1, le=10)
    include_historical_context: bool = False

    @field_validator("normalized_question")
    @classmethod
    def require_normalized_question(cls, value: str) -> str:
        if value != normalize_question(value):
            raise ValueError("normalized_question must use canonical lowercase token spacing")
        return value

    @model_validator(mode="after")
    def require_trusted_subset_and_safe_selection(self) -> RetrievalRequest:
        permission_ids = tuple(permission.root for permission in self.trusted_permissions)
        if len(permission_ids) != len(set(permission_ids)):
            raise ValueError("trusted permissions must be unique")
        context_permissions = {permission.root for permission in self.context.permissions}
        if not set(permission_ids).issubset(context_permissions):
            raise ValueError("trusted permissions must be a subset of resolved context permissions")
        if self.selected_entity_type is not None:
            selected_entity = self.context.selected_entity
            if selected_entity is None or selected_entity.entity_type != self.selected_entity_type:
                raise ValueError("selected entity type must match the resolved context")
        return self


class RetrievalResult(DomainModel):
    """Inspectable retrieval outcome, including an explicit no-source result."""

    data_policy: ClassVar[ModelDataPolicy] = RetrievalRequest.data_policy

    intent: RetrievalIntent
    sources: tuple[RetrievedSource, ...] = Field(default=(), max_length=10)
    no_source_reason: ShortText | None = None
    candidate_count: int = Field(ge=0)
    permission_filtered_count: int = Field(ge=0)

    @model_validator(mode="after")
    def require_consistent_source_outcome(self) -> RetrievalResult:
        if self.sources and self.no_source_reason is not None:
            raise ValueError("a grounded result cannot carry a no-source reason")
        if not self.sources and self.no_source_reason is None:
            raise ValueError("an empty result must explain why no source was returned")
        return self
