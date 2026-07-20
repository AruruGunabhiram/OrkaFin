"""Provider-output allowlists and fail-closed post-validation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from orkafin.domain.privacy import contains_sensitive_text
from orkafin.providers.contracts import (
    ClaimKind,
    DraftKind,
    ProviderDraft,
    ProviderRequest,
)
from orkafin.providers.grounding import ClaimGroundingChecker, ClaimGroundingError

_SUCCESS_ASSERTION = re.compile(
    r"(?:\b(?:i|we)\s+(?:successfully\s+)?(?:created|deleted|executed|updated)\b|"
    r"\b(?:action|change|request|update)\s+(?:succeeded|was successful|is complete)\b|"
    r"\b(?:has|have|was|were)\s+(?:successfully\s+)?(?:created|deleted|executed|updated)\b)",
    re.IGNORECASE,
)


class ProviderDraftRejected(ValueError):
    """A provider draft was outside a server-owned output or grounding allowlist."""


@dataclass(frozen=True, slots=True)
class ProviderOutputAllowlist:
    """Inspectable IDs and response kinds derived only from a trusted request."""

    response_kinds: frozenset[DraftKind]
    source_ids: frozenset[str]
    feature_ids: frozenset[str]
    action_ids: frozenset[str]
    receipt_ids: frozenset[str]

    @classmethod
    def from_request(cls, request: ProviderRequest) -> ProviderOutputAllowlist:
        return cls(
            response_kinds=frozenset(request.constraints.allowed_kinds),
            source_ids=frozenset(source.source_id for source in request.sources),
            feature_ids=frozenset(request.constraints.allowed_feature_ids),
            action_ids=frozenset(request.constraints.allowed_action_ids),
            receipt_ids=frozenset(request.constraints.allowed_receipt_ids),
        )


class ProviderOutputValidator:
    """Reject ungrounded drafts before they can become assistant responses."""

    def __init__(self, grounding_checker: ClaimGroundingChecker | None = None) -> None:
        self._grounding_checker = grounding_checker or ClaimGroundingChecker()

    def validate(self, draft: ProviderDraft, request: ProviderRequest) -> None:
        """Enforce kind, ID, citation, step, claim, and success boundaries."""
        allowlist = ProviderOutputAllowlist.from_request(request)
        if draft.kind not in allowlist.response_kinds:
            raise ProviderDraftRejected("provider chose a response kind outside server constraints")
        if len(draft.steps) > request.constraints.max_steps:
            raise ProviderDraftRejected("provider exceeded the step limit")
        if len(draft.cited_source_ids) != len(set(draft.cited_source_ids)):
            raise ProviderDraftRejected("provider cited a source more than once")
        if not set(draft.cited_source_ids).issubset(allowlist.source_ids):
            raise ProviderDraftRejected("provider cited an unknown source")

        grounded = draft.kind in {DraftKind.GROUNDED_GUIDANCE, DraftKind.VERIFIED_FACT}
        if grounded and not draft.cited_source_ids:
            raise ProviderDraftRejected("grounded provider draft requires citations")
        if request.constraints.require_citations and grounded and not draft.cited_source_ids:
            raise ProviderDraftRejected("server policy requires grounded citations")
        if not grounded and draft.cited_source_ids:
            raise ProviderDraftRejected("non-grounded provider draft cannot cite sources")

        feature_ids = {feature_id for claim in draft.claims for feature_id in claim.feature_ids}
        action_ids = {action_id for claim in draft.claims for action_id in claim.action_ids}
        receipt_ids = {receipt_id for claim in draft.claims for receipt_id in claim.receipt_ids}
        if not feature_ids.issubset(allowlist.feature_ids):
            raise ProviderDraftRejected("provider used a feature outside the allowlist")
        if not action_ids.issubset(allowlist.action_ids):
            raise ProviderDraftRejected("provider suggested an action outside the allowlist")
        if not receipt_ids.issubset(allowlist.receipt_ids):
            raise ProviderDraftRejected("provider used a receipt outside the allowlist")
        if any(claim.kind is ClaimKind.ACTION_SUCCESS for claim in draft.claims):
            raise ProviderDraftRejected("provider output cannot attest action success")
        if contains_sensitive_text(" ".join((draft.text, *draft.steps))):
            raise ProviderDraftRejected("provider output contains sensitive text")

        # This narrow phrase recognizer is defense in depth for a provider that lies
        # about its structured claim kind; trust boundaries and allowlists remain primary.
        if grounded and _SUCCESS_ASSERTION.search(" ".join((draft.text, *draft.steps))):
            raise ProviderDraftRejected("provider output asserted action success")

        if grounded:
            try:
                self._grounding_checker.check(draft, request)
            except ClaimGroundingError as error:
                raise ProviderDraftRejected("provider claims are not grounded") from error
