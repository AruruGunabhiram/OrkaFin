"""Deliberately bounded scalar metadata for events and audits."""

from __future__ import annotations

import json
import math
from typing import Annotated, ClassVar

from pydantic import (
    ConfigDict,
    RootModel,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)

from orkafin.domain.base import (
    DataClassification,
    DataOwner,
    ModelDataPolicy,
    PersistencePolicy,
)

MetadataKey = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=48,
        pattern=r"^[a-z][a-z0-9_]*$",
        strict=True,
    ),
]
MetadataValue = StrictStr | StrictInt | StrictFloat | StrictBool | None

_FORBIDDEN_KEY_PARTS = frozenset(
    {
        "authorization",
        "cookie",
        "email",
        "notes",
        "password",
        "prompt",
        "raw_content",
        "secret",
        "token",
    }
)


class BoundedMetadata(RootModel[dict[MetadataKey, MetadataValue]]):
    """Small scalar-only metadata map with privacy and serialized-size limits."""

    model_config = ConfigDict(frozen=True, strict=True)
    data_policy: ClassVar[ModelDataPolicy] = ModelDataPolicy(
        owner=DataOwner.ORKAFIN,
        classification=DataClassification.CONFIDENTIAL,
        persistence=PersistencePolicy.ORKAFIN_ALLOWED,
    )

    @model_validator(mode="after")
    def validate_bounds(self) -> BoundedMetadata:
        if len(self.root) > 16:
            raise ValueError("metadata may contain at most 16 entries")
        for key, value in self.root.items():
            if any(part in key for part in _FORBIDDEN_KEY_PARTS):
                raise ValueError(f"metadata key is not allowed: {key}")
            if isinstance(value, str) and len(value) > 256:
                raise ValueError("metadata string values may contain at most 256 characters")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("metadata numbers must be finite")
        serialized = json.dumps(self.root, separators=(",", ":"), sort_keys=True)
        if len(serialized.encode("utf-8")) > 2_048:
            raise ValueError("metadata serialized size may not exceed 2048 bytes")
        return self
