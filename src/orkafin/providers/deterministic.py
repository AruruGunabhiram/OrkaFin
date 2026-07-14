"""Offline response provider with stable templates for Local V1."""

from __future__ import annotations

from orkafin.providers.contracts import DraftKind, ProviderDraft, ProviderRequest, ResponseIntent


class DeterministicResponseProvider:
    """Produce predictable wording from approved sources and safe context only."""

    def generate(self, request: ProviderRequest) -> ProviderDraft:
        """Format the server-selected response intent without inferring permissions."""
        if request.intent is ResponseIntent.REFUSAL:
            return ProviderDraft(
                kind=DraftKind.REFUSAL,
                text="I cannot provide that information with the verified access for this request.",
                template_id="refusal_verified_access",
            )
        if not request.sources:
            return ProviderDraft(
                kind=DraftKind.UNAVAILABLE_INFORMATION,
                text="Approved information is not available for this request.",
                template_id=(
                    "unknown_no_approved_source"
                    if request.intent is ResponseIntent.UNKNOWN
                    else "unavailable_no_approved_source"
                ),
            )

        primary = request.sources[0]
        citation_ids = (primary.source_id,)
        if request.intent is ResponseIntent.EXPLAIN_PAGE:
            return ProviderDraft(
                kind=DraftKind.GROUNDED_GUIDANCE,
                text=f"{primary.title}: {primary.excerpt}",
                cited_source_ids=citation_ids,
                template_id="explain_page_v1",
            )
        if request.intent is ResponseIntent.AVAILABLE_ACTIONS:
            return ProviderDraft(
                kind=DraftKind.GROUNDED_GUIDANCE,
                text=f"On {request.context.page_id}, the approved guidance is: {primary.excerpt}",
                cited_source_ids=citation_ids,
                template_id="available_actions_v1",
            )
        if request.intent is ResponseIntent.STEP_BY_STEP_HELP:
            steps = (primary.excerpt,)
            return ProviderDraft(
                kind=DraftKind.GROUNDED_GUIDANCE,
                text=f"Follow the approved guidance for {primary.title}.",
                steps=steps,
                cited_source_ids=citation_ids,
                template_id="step_by_step_help_v1",
            )
        if request.intent is ResponseIntent.CANDIDATE_SUMMARY:
            if request.context.candidate_fields:
                details = "; ".join(
                    f"{field.label}: {field.value}" for field in request.context.candidate_fields
                )
                return ProviderDraft(
                    kind=DraftKind.VERIFIED_FACT,
                    text=f"Authorized candidate summary: {details}",
                    cited_source_ids=citation_ids,
                    template_id="candidate_summary_v1",
                )
            return ProviderDraft(
                kind=DraftKind.UNAVAILABLE_INFORMATION,
                text="An authorized candidate summary is not available for this request.",
                template_id="candidate_summary_unavailable",
            )
        if request.intent is ResponseIntent.UNCERTAINTY:
            return ProviderDraft(
                kind=DraftKind.GROUNDED_GUIDANCE,
                text=(
                    f"Available approved guidance for {primary.title} is limited: {primary.excerpt}"
                ),
                cited_source_ids=citation_ids,
                template_id="uncertainty_grounded_v1",
            )
        return ProviderDraft(
            kind=DraftKind.UNAVAILABLE_INFORMATION,
            text="Approved information is not available for this request.",
            template_id="unknown_no_approved_source",
        )
