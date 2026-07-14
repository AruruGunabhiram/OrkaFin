"""Explainable, deterministic matching against the controlled knowledge index."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from orkafin.application.retrieval.models import (
    RetrievalIntent,
    RetrievalRequest,
    RetrievalResult,
    normalize_question,
)
from orkafin.domain.base import DataOwner
from orkafin.domain.catalog import (
    CatalogProvenance,
    CatalogStatus,
    FeatureCatalogItem,
    HelpArticle,
    PageCatalogItem,
    VerificationStatus,
)
from orkafin.domain.identifiers import Permission
from orkafin.domain.sources import RetrievedSource, SourceType
from orkafin.knowledge import KnowledgeIndex

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_TOKENS = frozenset(
    {
        "a",
        "about",
        "an",
        "and",
        "can",
        "do",
        "explain",
        "for",
        "here",
        "how",
        "i",
        "is",
        "me",
        "please",
        "show",
        "tell",
        "the",
        "this",
        "to",
        "what",
    }
)


class _CatalogItem(Protocol):
    app_id: str
    aliases: tuple[str, ...]
    required_permissions: tuple[Permission, ...]
    provenance: CatalogProvenance


@dataclass(frozen=True, slots=True)
class _Candidate:
    item: PageCatalogItem | FeatureCatalogItem | HelpArticle
    source_id: str
    source_type: SourceType
    title: str
    excerpt: str
    identifiers: tuple[str, ...]
    aliases: tuple[str, ...]
    tags: tuple[str, ...]
    context_page_ids: tuple[str, ...]
    page_links: tuple[str, ...]
    feature_links: tuple[str, ...]
    searchable_text: str


@dataclass(frozen=True, slots=True)
class _RankedCandidate:
    candidate: _Candidate
    tier: int
    raw_score: int
    reason: str


class DeterministicRetrievalService:
    """Retrieve only active, catalog-approved, permission-filtered source records."""

    def __init__(
        self,
        *,
        knowledge_index: KnowledgeIndex,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._knowledge_index = knowledge_index
        self._clock = clock or (lambda: datetime.now(UTC))

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Return ranked sources, or an explicit empty result when no source is safe."""
        if request.context.app.app_id != self._knowledge_index.manifest.app_id:
            return RetrievalResult(
                intent=RetrievalIntent.UNKNOWN_FEATURE,
                no_source_reason="No approved sources are available for this application context.",
                candidate_count=0,
                permission_filtered_count=0,
            )

        requested_intent = self._match_intent(request.normalized_question)
        candidates = tuple(self._iter_candidates(request.include_historical_context))
        permitted, permission_filtered_count = self._filter_permissions(
            candidates, request.trusted_permissions
        )
        ranked = tuple(
            ranked
            for candidate in permitted
            if (
                ranked := self._score(
                    candidate,
                    normalized_question=request.normalized_question,
                    context_page_id=request.context.page_id,
                    intent=requested_intent,
                )
            )
            is not None
        )
        if not ranked:
            denied_match_exists = any(
                self._score(
                    candidate,
                    normalized_question=request.normalized_question,
                    context_page_id=request.context.page_id,
                    intent=requested_intent,
                )
                is not None
                for candidate in candidates
                if candidate not in permitted
            )
            no_source_reason = (
                "No approved sources are available for the verified permissions."
                if denied_match_exists and permission_filtered_count
                else "No active approved source matched the question."
            )
            return RetrievalResult(
                intent=RetrievalIntent.UNKNOWN_FEATURE,
                no_source_reason=no_source_reason,
                candidate_count=len(candidates),
                permission_filtered_count=permission_filtered_count,
            )

        source_order = {
            SourceType.PAGE_CATALOG: 0,
            SourceType.FEATURE_CATALOG: 1,
            SourceType.HELP_ARTICLE: 2,
        }
        ordered = sorted(
            ranked,
            key=lambda value: (
                -value.tier,
                -value.raw_score,
                source_order[value.candidate.source_type],
                value.candidate.source_id,
            ),
        )
        return RetrievalResult(
            intent=requested_intent,
            sources=tuple(self._to_source(value) for value in ordered[: request.limit]),
            candidate_count=len(candidates),
            permission_filtered_count=permission_filtered_count,
        )

    @staticmethod
    def _match_intent(question: str) -> RetrievalIntent:
        if any(phrase in question for phrase in ("step by step", "how do i", "how to", "walk me")):
            return RetrievalIntent.STEP_BY_STEP_HELP
        if any(
            phrase in question
            for phrase in ("what can i do here", "what can i do", "available actions")
        ):
            return RetrievalIntent.WHAT_CAN_I_DO_HERE
        if any(phrase in question for phrase in ("explain this page", "this page", "explain page")):
            return RetrievalIntent.EXPLAIN_THIS_PAGE
        return RetrievalIntent.FEATURE_QUESTION

    def _iter_candidates(self, include_historical: bool) -> Iterable[_Candidate]:
        allowed_statuses = {CatalogStatus.ACTIVE}
        if include_historical:
            allowed_statuses.add(CatalogStatus.DEPRECATED)
        for page in self._knowledge_index.pages:
            if page.provenance.status in allowed_statuses:
                yield _page_candidate(page)
        for feature in self._knowledge_index.features:
            if feature.provenance.status in allowed_statuses:
                yield _feature_candidate(feature)
        for article in self._knowledge_index.help_articles:
            if article.provenance.status in allowed_statuses:
                yield _help_candidate(article)

    @staticmethod
    def _filter_permissions(
        candidates: Iterable[_Candidate], trusted_permissions: tuple[Permission, ...]
    ) -> tuple[tuple[_Candidate, ...], int]:
        granted = {permission.root for permission in trusted_permissions}
        permitted: list[_Candidate] = []
        rejected = 0
        for candidate in candidates:
            if {permission.root for permission in candidate.item.required_permissions}.issubset(
                granted
            ):
                permitted.append(candidate)
            else:
                rejected += 1
        return tuple(permitted), rejected

    @staticmethod
    def _score(
        candidate: _Candidate,
        *,
        normalized_question: str,
        context_page_id: str,
        intent: RetrievalIntent,
    ) -> _RankedCandidate | None:
        query_tokens = set(_meaningful_tokens(normalized_question))
        score = 0
        tier = 0
        reasons: list[str] = []
        identifier_matches = _exact_matches(normalized_question, candidate.identifiers)
        alias_matches = _exact_matches(normalized_question, candidate.aliases)
        if identifier_matches:
            score += 100 + _longest_match_bonus(identifier_matches)
            tier = 3
            reasons.append("exact ID or title match")
        elif alias_matches:
            score += 90 + _longest_match_bonus(alias_matches)
            tier = 3
            reasons.append("exact alias match")

        linked_query_pages = _exact_matches(normalized_question, candidate.page_links)
        linked_query_features = _exact_matches(normalized_question, candidate.feature_links)
        if linked_query_pages or linked_query_features:
            score += 55
            tier = max(tier, 2)
            reasons.append("linked page or feature match")

        tag_matches = _exact_matches(
            normalized_question,
            tuple(tag for tag in candidate.tags if len(normalize_question(tag).split()) > 1),
        )
        if tag_matches:
            score += 35
            tier = max(tier, 2)
            reasons.append("exact help tag match")

        candidate_tokens = set(_meaningful_tokens(candidate.searchable_text))
        overlap = query_tokens.intersection(candidate_tokens)
        if overlap:
            score += min(30, len(overlap) * 10)
            tier = max(tier, 1)
            reasons.append(f"token match: {', '.join(sorted(overlap))}")

        has_strong_query_match = tier >= 2 or len(overlap) >= min(2, len(query_tokens))
        context_only_intent = intent in {
            RetrievalIntent.EXPLAIN_THIS_PAGE,
            RetrievalIntent.WHAT_CAN_I_DO_HERE,
        }
        direct_context_match = context_page_id in candidate.context_page_ids
        related_context_match = context_page_id in candidate.page_links
        if context_only_intent or has_strong_query_match:
            if direct_context_match:
                score += 40
                tier = max(tier, 2)
                reasons.append("current page context match")
            elif related_context_match:
                score += 20
                tier = max(tier, 2)
                reasons.append("related page context match")

        if (
            intent is RetrievalIntent.STEP_BY_STEP_HELP
            and candidate.source_type is SourceType.HELP_ARTICLE
        ):
            score += 8
            reasons.append("help intent")
        elif (
            intent is RetrievalIntent.EXPLAIN_THIS_PAGE
            and candidate.source_type is SourceType.PAGE_CATALOG
        ):
            score += 8
            reasons.append("page explanation intent")
        elif intent is RetrievalIntent.WHAT_CAN_I_DO_HERE and direct_context_match:
            if candidate.source_type is SourceType.PAGE_CATALOG:
                score += 16
            else:
                score += 6
            reasons.append("available guidance for current page")

        # A context-only query is intentionally supported for explain/available guidance.
        if tier == 0 or (
            not context_only_intent and tier < 2 and len(overlap) < min(2, len(query_tokens))
        ):
            return None
        return _RankedCandidate(
            candidate=candidate,
            tier=tier,
            raw_score=score,
            reason="; ".join(reasons),
        )

    def _to_source(self, ranked: _RankedCandidate) -> RetrievedSource:
        item = ranked.candidate.item
        provenance = item.provenance
        uncertainty_reason = _uncertainty_reason(item, ranked)
        return RetrievedSource(
            source_id=ranked.candidate.source_id,
            source_type=ranked.candidate.source_type,
            source_owner=DataOwner.PRODUCT_DOCUMENTATION,
            app_id=item.app_id,
            content_version=provenance.content_version,
            revision=provenance.revision,
            title=ranked.candidate.title,
            safe_reference=provenance.safe_reference,
            excerpt=ranked.candidate.excerpt,
            verification_status=provenance.verification_status,
            relevance_score=min(ranked.raw_score / 300, 1.0),
            relevance_reason=ranked.reason,
            required_permissions=item.required_permissions,
            uncertainty_reason=uncertainty_reason,
            retrieved_at=self._clock(),
        )


def _page_candidate(item: PageCatalogItem) -> _Candidate:
    return _Candidate(
        item=item,
        source_id=item.page_id,
        source_type=SourceType.PAGE_CATALOG,
        title=item.title,
        excerpt=item.purpose,
        identifiers=(item.page_id, item.title),
        aliases=item.aliases,
        tags=(),
        context_page_ids=(item.page_id,),
        page_links=(item.page_id, *item.related_page_ids),
        feature_links=(*item.feature_ids, *item.related_feature_ids),
        searchable_text=" ".join(
            (item.page_id, item.title, item.purpose, *item.aliases, *item.feature_ids)
        ),
    )


def _feature_candidate(item: FeatureCatalogItem) -> _Candidate:
    return _Candidate(
        item=item,
        source_id=item.feature_id,
        source_type=SourceType.FEATURE_CATALOG,
        title=item.name,
        excerpt=item.description,
        identifiers=(item.feature_id, item.name),
        aliases=item.aliases,
        tags=(),
        context_page_ids=item.page_ids,
        page_links=item.page_ids,
        feature_links=(item.feature_id, *item.related_feature_ids),
        searchable_text=" ".join(
            (
                item.feature_id,
                item.name,
                item.description,
                item.user_purpose,
                *item.aliases,
                *item.page_ids,
            )
        ),
    )


def _help_candidate(item: HelpArticle) -> _Candidate:
    return _Candidate(
        item=item,
        source_id=item.article_id,
        source_type=SourceType.HELP_ARTICLE,
        title=item.title,
        excerpt=_safe_excerpt(item.summary, item.content),
        identifiers=(item.article_id, item.title),
        aliases=item.aliases,
        tags=item.tags,
        context_page_ids=item.page_ids,
        page_links=item.page_ids,
        feature_links=item.feature_ids,
        searchable_text=" ".join(
            (
                item.article_id,
                item.title,
                item.summary,
                item.purpose,
                item.content,
                *item.aliases,
                *item.tags,
                *item.page_ids,
                *item.feature_ids,
            )
        ),
    )


def _safe_excerpt(summary: str, content: str) -> str:
    """Bound article excerpts; source text remains data and is never interpreted."""
    compact = " ".join(content.split())
    suffix = compact[:360].rstrip()
    return f"{summary} {suffix}"[:500].rstrip()


def _meaningful_tokens(value: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _TOKEN_PATTERN.findall(normalize_question(value))
        if token not in _STOP_TOKENS
    )


def _exact_matches(question: str, values: Iterable[str]) -> tuple[str, ...]:
    padded_question = f" {question} "
    matches = []
    for value in values:
        canonical = normalize_question(value)
        if canonical and f" {canonical} " in padded_question:
            matches.append(canonical)
    return tuple(matches)


def _longest_match_bonus(matches: Iterable[str]) -> int:
    return max((len(value.split()) * 15 for value in matches), default=0)


def _uncertainty_reason(
    item: PageCatalogItem | FeatureCatalogItem | HelpArticle, ranked: _RankedCandidate
) -> str | None:
    if item.provenance.verification_status is VerificationStatus.VERIFIED:
        return None
    if not item.instruction_steps and "help intent" in ranked.reason:
        return "This related source is provisional and does not verify step-by-step instructions."
    return "This source is provisional; exact controls and workflow details are not verified."
