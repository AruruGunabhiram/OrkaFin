"""Public V1 API envelopes that compose existing domain contracts."""

from typing import ClassVar

from pydantic import Field

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    DomainModel,
    ModelDataPolicy,
    PersistencePolicy,
)
from orkafin.domain.catalog import FeatureCatalogItem
from orkafin.domain.context import AppMetadata
from orkafin.domain.conversations import Conversation, Message


class FeatureCatalogResponse(DomainModel):
    """Controlled catalog listing, not a claim that every feature is authorized now."""

    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.INTERNAL,
        persistence=PersistencePolicy.NEVER,
    )

    app: AppMetadata
    features: tuple[FeatureCatalogItem, ...] = Field(max_length=100)


class ConversationResponse(DomainModel):
    """Verified-owner view of one OrkaFin-owned conversation."""

    data_policy: ClassVar[ModelDataPolicy] = FeatureCatalogResponse.data_policy

    conversation: Conversation
    messages: tuple[Message, ...] = Field(max_length=500)
