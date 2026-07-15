"""Claim-to-source grounding checks independent of provider implementation."""

from __future__ import annotations

import re

from orkafin.domain.catalog import VerificationStatus
from orkafin.domain.sources import SourceType
from orkafin.providers.contracts import (
    ClaimKind,
    ClaimOutputField,
    ProviderClaim,
    ProviderDraft,
    ProviderRequest,
    ResponseIntent,
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_SAFE_CONNECTIVE_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "approved",
        "authorized",
        "available",
        "candidate",
        "details",
        "follow",
        "for",
        "guidance",
        "is",
        "limited",
        "on",
        "source",
        "steps",
        "summary",
        "the",
        "this",
        "to",
    }
)


class ClaimGroundingError(ValueError):
    """A structured claim did not map to supplied server-approved evidence."""


class ClaimGroundingChecker:
    """Require complete output coverage and category-appropriate evidence."""

    def check(self, draft: ProviderDraft, request: ProviderRequest) -> None:
        """Validate every grounded output field against its declared source mapping."""
        source_lookup = {source.source_id: source for source in request.sources}
        locations: dict[tuple[ClaimOutputField, int | None], ProviderClaim] = {}
        for claim in draft.claims:
            location = (claim.output_field, claim.step_index)
            if location in locations:
                raise ClaimGroundingError("each provider output field must have exactly one claim")
            locations[location] = claim
            if not set(claim.source_ids).issubset(source_lookup):
                raise ClaimGroundingError("claim references an unknown source")
            self._check_claim_category(claim, request)
            self._check_lexical_support(claim, request)

        expected_locations = {(ClaimOutputField.TEXT, None)} | {
            (ClaimOutputField.STEP, index) for index in range(len(draft.steps))
        }
        if set(locations) != expected_locations:
            raise ClaimGroundingError("claims must cover the text and every step exactly once")
        for location, claim in locations.items():
            output_text = (
                draft.text
                if location[0] is ClaimOutputField.TEXT
                else draft.steps[location[1] if location[1] is not None else 0]
            )
            if claim.text != output_text:
                raise ClaimGroundingError("claim text must exactly match its covered output field")

        claimed_source_ids = {source_id for claim in draft.claims for source_id in claim.source_ids}
        if claimed_source_ids != set(draft.cited_source_ids):
            raise ClaimGroundingError("draft citations must exactly match structured claim sources")

    @staticmethod
    def _check_claim_category(claim: ProviderClaim, request: ProviderRequest) -> None:
        sources = tuple(
            source for source in request.sources if source.source_id in set(claim.source_ids)
        )
        source_types = {source.source_type for source in sources}
        if (
            any(source.verification_status is not VerificationStatus.VERIFIED for source in sources)
            and request.intent is not ResponseIntent.UNCERTAINTY
        ):
            raise ClaimGroundingError("unverified sources require the uncertainty intent")
        if claim.kind is ClaimKind.PRODUCT_FACT:
            if not source_types.intersection({SourceType.APP_METADATA, SourceType.PAGE_CATALOG}):
                raise ClaimGroundingError("product facts require app or page catalog evidence")
            _reject_irrelevant_ids(claim)
        elif claim.kind is ClaimKind.FEATURE_FACT:
            if not claim.feature_ids:
                raise ClaimGroundingError("feature facts require explicit feature IDs")
            if not set(claim.feature_ids).issubset(request.constraints.allowed_feature_ids):
                raise ClaimGroundingError("feature claim is outside the feature-ID allowlist")
            backed_feature_ids = {
                feature_id for source in sources for feature_id in source.feature_ids
            }
            if not set(claim.feature_ids).issubset(backed_feature_ids):
                raise ClaimGroundingError("feature claim lacks matching catalog evidence")
            if claim.action_ids or claim.receipt_ids:
                raise ClaimGroundingError("feature facts cannot carry action or receipt IDs")
        elif claim.kind is ClaimKind.HELP_FACT:
            if SourceType.HELP_ARTICLE not in source_types:
                raise ClaimGroundingError("help facts require an approved help source")
            _reject_irrelevant_ids(claim)
        elif claim.kind is ClaimKind.CANDIDATE_FACT:
            if SourceType.CANDIDATE_SUMMARY not in source_types:
                raise ClaimGroundingError("candidate facts require an adapter summary source")
            if not request.context.candidate_fields:
                raise ClaimGroundingError("candidate facts require supplied verified fields")
            _reject_irrelevant_ids(claim)
        elif claim.kind is ClaimKind.ACTION_SUGGESTION:
            if not claim.action_ids:
                raise ClaimGroundingError("action suggestions require explicit action IDs")
            if not set(claim.action_ids).issubset(request.constraints.allowed_action_ids):
                raise ClaimGroundingError("action suggestion is outside the action-ID allowlist")
            backed_action_ids = {action_id for source in sources for action_id in source.action_ids}
            if not set(claim.action_ids).issubset(backed_action_ids):
                raise ClaimGroundingError("action suggestion lacks matching definition evidence")
            if claim.feature_ids or claim.receipt_ids:
                raise ClaimGroundingError("action suggestions cannot carry feature or receipt IDs")
        else:
            # Provider prose is never the action-result channel. A typed execution
            # result built from an adapter receipt owns that assertion elsewhere.
            raise ClaimGroundingError("providers cannot author action-success claims")

        if claim.output_field is ClaimOutputField.STEP and not any(
            claim.text in source.approved_steps for source in sources
        ):
            raise ClaimGroundingError("provider step is not an approved verified instruction")

    @staticmethod
    def _check_lexical_support(claim: ProviderClaim, request: ProviderRequest) -> None:
        """Apply a conservative secondary check without trusting question/history words."""
        sources = tuple(
            source for source in request.sources if source.source_id in set(claim.source_ids)
        )
        approved_parts = [
            part
            for source in sources
            for part in (source.title, source.excerpt, *source.approved_steps)
        ]
        approved_parts.extend((request.context.app_name, request.context.page_id))
        if claim.kind is ClaimKind.CANDIDATE_FACT:
            approved_parts.extend(
                f"{field.label} {field.value}" for field in request.context.candidate_fields
            )
        allowed_tokens = set(_TOKEN_PATTERN.findall(" ".join(approved_parts).lower()))
        allowed_tokens.update(_SAFE_CONNECTIVE_WORDS)
        unsupported = {
            token
            for token in _TOKEN_PATTERN.findall(claim.text.lower())
            if len(token) >= 4 and token not in allowed_tokens
        }
        if unsupported:
            raise ClaimGroundingError("claim introduces terms absent from approved evidence")


def _reject_irrelevant_ids(claim: ProviderClaim) -> None:
    if claim.feature_ids or claim.action_ids or claim.receipt_ids:
        raise ClaimGroundingError("claim category contains unrelated allowlisted IDs")
