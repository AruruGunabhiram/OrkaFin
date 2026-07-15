"""Offline response provider with stable, claim-annotated Local V1 templates."""

from __future__ import annotations

from orkafin.domain.sources import SourceType
from orkafin.providers.contracts import (
    ApprovedProviderSource,
    ClaimKind,
    ClaimOutputField,
    DraftKind,
    ProviderClaim,
    ProviderDraft,
    ProviderRequest,
    ResponseIntent,
)


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
            return _unavailable(
                "unknown_no_approved_source"
                if request.intent is ResponseIntent.UNKNOWN
                else "unavailable_no_approved_source"
            )
        if request.intent is ResponseIntent.UNKNOWN:
            return _unavailable("unknown_no_approved_source")

        if request.intent is ResponseIntent.CANDIDATE_SUMMARY:
            candidate_source = next(
                (
                    source
                    for source in request.sources
                    if source.source_type is SourceType.CANDIDATE_SUMMARY
                ),
                None,
            )
            if candidate_source is None or not request.context.candidate_fields:
                return ProviderDraft(
                    kind=DraftKind.UNAVAILABLE_INFORMATION,
                    text="An authorized candidate summary is not available for this request.",
                    template_id="candidate_summary_unavailable",
                )
            text = _candidate_summary_text(request)
            return ProviderDraft(
                kind=DraftKind.VERIFIED_FACT,
                text=text,
                cited_source_ids=(candidate_source.source_id,),
                claims=(_claim(text, candidate_source, request),),
                template_id="candidate_summary_v1",
            )

        if request.intent is ResponseIntent.AVAILABLE_ACTIONS:
            action_source = next(
                (
                    source
                    for source in request.sources
                    if set(source.action_ids).intersection(request.constraints.allowed_action_ids)
                ),
                None,
            )
            if action_source is None:
                return ProviderDraft(
                    kind=DraftKind.UNAVAILABLE_INFORMATION,
                    text="Approved actions are not available for this request.",
                    template_id="available_actions_unavailable",
                )
            text = f"{action_source.title}: {action_source.excerpt}"
            return ProviderDraft(
                kind=DraftKind.GROUNDED_GUIDANCE,
                text=text,
                cited_source_ids=(action_source.source_id,),
                claims=(_claim(text, action_source, request),),
                template_id="available_actions_v1",
            )

        if request.intent is ResponseIntent.STEP_BY_STEP_HELP:
            step_source = next(
                (source for source in request.sources if source.approved_steps), None
            )
            if step_source is None:
                return ProviderDraft(
                    kind=DraftKind.UNAVAILABLE_INFORMATION,
                    text="Verified step-by-step guidance is not available for this request.",
                    template_id="step_by_step_help_unavailable",
                )
            steps = step_source.approved_steps[: request.constraints.max_steps]
            text = f"Follow the approved steps for {step_source.title}."
            claims = [_claim(text, step_source, request)]
            claims.extend(
                _claim(
                    step,
                    step_source,
                    request,
                    output_field=ClaimOutputField.STEP,
                    step_index=index,
                )
                for index, step in enumerate(steps)
            )
            return ProviderDraft(
                kind=DraftKind.GROUNDED_GUIDANCE,
                text=text,
                steps=steps,
                cited_source_ids=(step_source.source_id,),
                claims=tuple(claims),
                template_id="step_by_step_help_v1",
            )

        primary = next(
            (
                source
                for source in request.sources
                if source.source_type is not SourceType.ACTION_DEFINITION
            ),
            None,
        )
        if primary is None:
            return _unavailable("unavailable_no_approved_source")

        if request.intent is ResponseIntent.EXPLAIN_PAGE:
            text = f"{primary.title}: {primary.excerpt}"
            template_id = "explain_page_v1"
        elif request.intent is ResponseIntent.UNCERTAINTY:
            text = f"Available approved guidance for {primary.title} is limited: {primary.excerpt}"
            template_id = "uncertainty_grounded_v1"
        else:
            return _unavailable("unknown_no_approved_source")
        return ProviderDraft(
            kind=DraftKind.GROUNDED_GUIDANCE,
            text=text,
            cited_source_ids=(primary.source_id,),
            claims=(_claim(text, primary, request),),
            template_id=template_id,
        )


def _claim(
    text: str,
    source: ApprovedProviderSource,
    request: ProviderRequest,
    *,
    output_field: ClaimOutputField = ClaimOutputField.TEXT,
    step_index: int | None = None,
) -> ProviderClaim:
    feature_ids: tuple[str, ...] = ()
    action_ids: tuple[str, ...] = ()
    if source.source_type is SourceType.FEATURE_CATALOG:
        kind = ClaimKind.FEATURE_FACT
        feature_ids = tuple(
            feature_id
            for feature_id in source.feature_ids
            if feature_id in request.constraints.allowed_feature_ids
        )
    elif source.source_type is SourceType.HELP_ARTICLE:
        kind = ClaimKind.HELP_FACT
    elif source.source_type is SourceType.CANDIDATE_SUMMARY:
        kind = ClaimKind.CANDIDATE_FACT
    elif source.source_type is SourceType.ACTION_DEFINITION:
        kind = ClaimKind.ACTION_SUGGESTION
        action_ids = tuple(
            action_id
            for action_id in source.action_ids
            if action_id in request.constraints.allowed_action_ids
        )
    else:
        kind = ClaimKind.PRODUCT_FACT
    return ProviderClaim(
        kind=kind,
        output_field=output_field,
        step_index=step_index,
        text=text,
        source_ids=(source.source_id,),
        feature_ids=feature_ids,
        action_ids=action_ids,
    )


def _candidate_summary_text(request: ProviderRequest) -> str:
    prefix = "Authorized candidate summary: "
    parts: list[str] = []
    for field in request.context.candidate_fields:
        part = f"{field.label}: {field.value}"
        candidate = prefix + "; ".join((*parts, part))
        if len(candidate) > 500:
            break
        parts.append(part)
    if not parts:
        field = request.context.candidate_fields[0]
        return f"{prefix}{field.label}: {field.value}"[:500].rstrip()
    return prefix + "; ".join(parts)


def _unavailable(template_id: str) -> ProviderDraft:
    return ProviderDraft(
        kind=DraftKind.UNAVAILABLE_INFORMATION,
        text="Approved information is not available for this request.",
        template_id=template_id,
    )
