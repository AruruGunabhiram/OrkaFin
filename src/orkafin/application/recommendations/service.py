"""Privacy-minimized event capture and deterministic recommendation workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import Field

from orkafin.application.context import TrustedContextResolutionService
from orkafin.core.config import Settings
from orkafin.core.errors import DomainError
from orkafin.domain.base import DomainModel, Identifier
from orkafin.domain.context import ClientContextHint, ResolvedPageContext
from orkafin.domain.events import EventSource, UserEvent, UserEventType
from orkafin.domain.identifiers import CorrelationId, RequestId
from orkafin.domain.metadata import BoundedMetadata
from orkafin.domain.recommendations import (
    FeedbackComment,
    Recommendation,
    RecommendationFeedback,
    RecommendationFeedbackType,
    RecommendationPreference,
    RecommendationStatus,
)
from orkafin.infrastructure.database.repositories import OrkaFinRepository
from orkafin.infrastructure.database.session import Database
from orkafin.knowledge import KnowledgeIndex
from orkafin.knowledge.models import RecommendationCatalogItem

_PUBLIC_EVENT_TYPES = frozenset(
    {UserEventType.APP_OPENED, UserEventType.PAGE_VIEWED, UserEventType.CANDIDATE_SELECTED}
)
_RECENT_EVENT_WINDOW = timedelta(days=30)


class MeaningfulEventRequest(DomainModel):
    """Browser input that is reduced to a server-bound product event."""

    event_type: UserEventType = Field(strict=False)
    context: ClientContextHint
    metadata: BoundedMetadata = Field(default_factory=lambda: BoundedMetadata(root={}))


class RecommendationEvaluationRequest(DomainModel):
    """Request deterministic evaluation using only navigation hints."""

    context: ClientContextHint


class FeedbackRequest(DomainModel):
    """Feedback is bound to a persisted recommendation owned by the current user."""

    recommendation_id: Identifier
    feedback_type: RecommendationFeedbackType = Field(strict=False)
    context: ClientContextHint
    comment: FeedbackComment | None = None
    preference: RecommendationPreference | None = Field(default=None, strict=False)


class RecommendationEvaluationResponse(DomainModel):
    recommendations: tuple[Recommendation, ...] = Field(default=(), max_length=10)
    suppressed_rule_ids: tuple[str, ...] = Field(default=(), max_length=100)
    preference: RecommendationPreference


class FeedbackResponse(DomainModel):
    recommendation_id: Identifier
    status: RecommendationStatus
    preference: RecommendationPreference
    suppressed_until: datetime | None = None


class EventNotAllowedError(DomainError):
    public_message = "This event type cannot be submitted from the browser."


class FeedbackUnavailableError(DomainError):
    status_code = 404
    public_message = "The requested feedback target is unavailable."


class MeaningfulEventService:
    """Store validated product events after binding them to a verified context."""

    def __init__(
        self,
        *,
        database: Database,
        context_service: TrustedContextResolutionService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._context_service = context_service
        self._clock = clock or (lambda: datetime.now(UTC))

    async def submit(self, value: MeaningfulEventRequest, *, request_id: RequestId) -> UserEvent:
        if value.event_type not in _PUBLIC_EVENT_TYPES:
            raise EventNotAllowedError
        context = await self._context_service.resolve(
            client_hint=value.context, request_id=request_id, include_candidate_summary=False
        )
        return self.record(
            context=context,
            event_type=value.event_type,
            metadata=value.metadata,
            request_id=request_id,
        )

    def record(
        self,
        *,
        context: ResolvedPageContext,
        event_type: UserEventType,
        metadata: BoundedMetadata,
        request_id: RequestId,
        now: datetime | None = None,
    ) -> UserEvent:
        occurred_at = now or self._clock()
        event = UserEvent(
            event_id=_new_id("event"),
            event_type=event_type,
            source=EventSource.ORKAFIN,
            app_id=context.app.app_id,
            actor_user_id=context.identity.user_id,
            workspace=context.workspace,
            entity_ref=(
                context.selected_entity if event_type is UserEventType.CANDIDATE_SELECTED else None
            ),
            metadata=metadata,
            occurred_at=occurred_at,
            received_at=occurred_at,
            request_id=request_id,
            correlation_id=CorrelationId(root=request_id.root),
        )
        with self._database.session_factory.begin() as session:
            OrkaFinRepository(session).append_user_event(event)
        return event


class RecommendationService:
    """Evaluate version-controlled rules without ML, clickstreams, or inference."""

    def __init__(
        self,
        *,
        database: Database,
        context_service: TrustedContextResolutionService,
        knowledge_index: KnowledgeIndex,
        settings: Settings,
        event_service: MeaningfulEventService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._context_service = context_service
        self._knowledge_index = knowledge_index
        self._settings = settings
        self._event_service = event_service
        self._clock = clock or (lambda: datetime.now(UTC))

    async def evaluate(
        self, value: RecommendationEvaluationRequest, *, request_id: RequestId
    ) -> RecommendationEvaluationResponse:
        context = await self._context_service.resolve(
            client_hint=value.context, request_id=request_id, include_candidate_summary=False
        )
        now = self._clock()
        # Evaluation is a meaningful page interaction, but never an auto-open command.
        self._event_service.record(
            context=context,
            event_type=UserEventType.PAGE_VIEWED,
            metadata=BoundedMetadata(root={"origin": "recommendation_evaluation"}),
            request_id=request_id,
            now=now,
        )
        available_features = frozenset(context.available_feature_ids)
        with self._database.session_factory.begin() as session:
            repository = OrkaFinRepository(session)
            preference = _preference_for(repository, context)
            if preference is RecommendationPreference.DISABLED:
                return RecommendationEvaluationResponse(preference=preference)
            recent_events = set(
                repository.list_recent_user_event_types(
                    user_id=context.identity.user_id,
                    workspace_id=context.workspace.workspace_id,
                    occurred_after=now - _RECENT_EVENT_WINDOW,
                )
            )
            recommendations: list[Recommendation] = []
            suppressed: list[str] = []
            for rule in self._knowledge_index.recommendations:
                if not _matches_rule(
                    rule=rule,
                    context=context,
                    available_features=available_features,
                    recent_events=recent_events,
                ):
                    continue
                if self._is_suppressed(
                    repository=repository,
                    rule_id=rule.rule_id,
                    context=context,
                    preference=preference,
                    now=now,
                    allow_recurrence=rule.allow_recurrence,
                    impression_window_seconds=rule.impression_window_seconds,
                    dismissal_suppression_seconds=rule.dismissal_suppression_seconds,
                ):
                    suppressed.append(rule.rule_id)
                    continue
                feature_id = rule.feature_ids[0] if rule.feature_ids else None
                feature = (
                    self._knowledge_index.features_by_id.get(feature_id) if feature_id else None
                )
                if feature is None:
                    # The loader prevents this; retain the guard for injected indexes.
                    continue
                recommendation = Recommendation(
                    recommendation_id=_new_id("recommendation"),
                    rule_id=rule.rule_id,
                    kind=rule.kind,
                    status=RecommendationStatus.SHOWN,
                    recipient_user_id=context.identity.user_id,
                    workspace=context.workspace,
                    title=rule.title,
                    body=rule.description,
                    rationale=(
                        f"Shown because you are on {context.page_id} and the recent "
                        f"{UserEventType.PAGE_VIEWED.value} event matches rule {rule.rule_id}."
                    ),
                    feature_id=feature.feature_id,
                    action_id=rule.action_id,
                    source_ids=(rule.rule_id, feature.feature_id),
                    source_references=(
                        rule.provenance.safe_reference,
                        feature.provenance.safe_reference,
                    ),
                    created_at=now,
                    request_id=request_id,
                )
                repository.add_recommendation(recommendation)
                repository.add_recommendation_impression(
                    impression_id=_new_id("impression"),
                    recommendation_id=recommendation.recommendation_id,
                    user_id=context.identity.user_id,
                    workspace_id=context.workspace.workspace_id,
                    request_id=request_id.root,
                    shown_at=now,
                )
                repository.append_user_event(
                    _event_for_context(
                        context=context,
                        event_type=UserEventType.RECOMMENDATION_SHOWN,
                        metadata=BoundedMetadata(root={"rule_id": rule.rule_id}),
                        request_id=request_id,
                        now=now,
                    )
                )
                recommendations.append(recommendation)
            return RecommendationEvaluationResponse(
                recommendations=tuple(recommendations),
                suppressed_rule_ids=tuple(suppressed),
                preference=preference,
            )

    async def submit_feedback(
        self, value: FeedbackRequest, *, request_id: RequestId
    ) -> FeedbackResponse:
        context = await self._context_service.resolve(
            client_hint=value.context, request_id=request_id, include_candidate_summary=False
        )
        now = self._clock()
        with self._database.session_factory.begin() as session:
            repository = OrkaFinRepository(session)
            stored = repository.get_recommendation_model(value.recommendation_id)
            if (
                stored is None
                or stored.recipient_user_id != context.identity.user_id
                or stored.workspace_id != context.workspace.workspace_id
                or stored.workspace_app_id != context.workspace.app_id
            ):
                raise FeedbackUnavailableError
            feedback = RecommendationFeedback(
                feedback_id=_new_id("feedback"),
                recommendation_id=value.recommendation_id,
                user_id=context.identity.user_id,
                workspace=context.workspace,
                feedback_type=value.feedback_type,
                comment=value.comment,
                submitted_at=now,
                request_id=request_id,
            )
            repository.add_recommendation_feedback(feedback)
            if value.feedback_type is RecommendationFeedbackType.ACCEPTED:
                stored.status = RecommendationStatus.ACCEPTED.value
            elif value.feedback_type is RecommendationFeedbackType.DISMISSED:
                stored.status = RecommendationStatus.DISMISSED.value
            preference = value.preference or _preference_for(repository, context)
            if value.preference is not None:
                repository.set_recommendation_preference(
                    user_id=context.identity.user_id,
                    workspace_id=context.workspace.workspace_id,
                    workspace_app_id=context.workspace.app_id,
                    preference=preference.value,
                    updated_at=now,
                )
            repository.append_user_event(
                _event_for_context(
                    context=context,
                    event_type=UserEventType.FEEDBACK_SUBMITTED,
                    metadata=BoundedMetadata(root={"feedback_type": value.feedback_type.value}),
                    request_id=request_id,
                    now=now,
                )
            )
            if value.feedback_type in {
                RecommendationFeedbackType.ACCEPTED,
                RecommendationFeedbackType.DISMISSED,
            }:
                repository.append_user_event(
                    _event_for_context(
                        context=context,
                        event_type=(
                            UserEventType.RECOMMENDATION_ACCEPTED
                            if value.feedback_type is RecommendationFeedbackType.ACCEPTED
                            else UserEventType.RECOMMENDATION_DISMISSED
                        ),
                        metadata=BoundedMetadata(root={"rule_id": stored.rule_id}),
                        request_id=request_id,
                        now=now,
                    )
                )
            suppressed_until = None
            if value.feedback_type is RecommendationFeedbackType.DISMISSED:
                rule = self._knowledge_index.recommendations_by_id.get(stored.rule_id)
                duration = (
                    rule.dismissal_suppression_seconds
                    if rule and rule.dismissal_suppression_seconds is not None
                    else self._settings.recommendation_dismissal_suppression_seconds
                )
                suppressed_until = now + timedelta(seconds=duration)
            return FeedbackResponse(
                recommendation_id=value.recommendation_id,
                status=RecommendationStatus(stored.status),
                preference=preference,
                suppressed_until=suppressed_until,
            )

    def _is_suppressed(
        self,
        *,
        repository: OrkaFinRepository,
        rule_id: str,
        context: ResolvedPageContext,
        preference: RecommendationPreference,
        now: datetime,
        allow_recurrence: bool,
        impression_window_seconds: int | None,
        dismissal_suppression_seconds: int | None,
    ) -> bool:
        user_id = context.identity.user_id
        workspace_id = context.workspace.workspace_id
        if not allow_recurrence and repository.has_feedback_type(
            rule_id=rule_id,
            user_id=user_id,
            workspace_id=workspace_id,
            feedback_type=RecommendationFeedbackType.ACCEPTED.value,
        ):
            return True
        latest = repository.list_recommendations_for_rule(
            rule_id=rule_id, user_id=user_id, workspace_id=workspace_id
        )
        if latest and latest[0].status == RecommendationStatus.DISMISSED.value:
            duration = (
                dismissal_suppression_seconds
                or self._settings.recommendation_dismissal_suppression_seconds
            )
            if _utc(latest[0].created_at) >= now - timedelta(seconds=duration):
                return True
        shown_at = repository.latest_impression_at(
            rule_id=rule_id, user_id=user_id, workspace_id=workspace_id
        )
        if shown_at is None:
            return False
        window = (
            impression_window_seconds or self._settings.recommendation_impression_window_seconds
        )
        if preference is RecommendationPreference.REDUCED:
            window *= self._settings.recommendation_reduced_window_multiplier
        return _utc(shown_at) >= now - timedelta(seconds=window)


def _matches_rule(
    *,
    rule: RecommendationCatalogItem,
    context: ResolvedPageContext,
    available_features: frozenset[str],
    recent_events: set[str],
) -> bool:
    from orkafin.domain.catalog import CatalogStatus

    if rule.provenance.status is not CatalogStatus.ACTIVE:
        return False
    if rule.page_ids and context.page_id not in rule.page_ids:
        return False
    if not set(rule.required_permissions).issubset(context.permissions):
        return False
    if rule.supported_roles and context.identity.role not in rule.supported_roles:
        return False
    if not rule.feature_ids or any(
        feature_id not in available_features for feature_id in rule.feature_ids
    ):
        return False
    if rule.action_id is not None and rule.action_id not in context.available_action_ids:
        return False
    return not rule.recent_event_types or bool(set(rule.recent_event_types) & recent_events)


def _preference_for(
    repository: OrkaFinRepository, context: ResolvedPageContext
) -> RecommendationPreference:
    stored = repository.get_recommendation_preference(
        user_id=context.identity.user_id, workspace_id=context.workspace.workspace_id
    )
    return (
        RecommendationPreference(stored) if stored is not None else RecommendationPreference.ENABLED
    )


def _event_for_context(
    *,
    context: ResolvedPageContext,
    event_type: UserEventType,
    metadata: BoundedMetadata,
    request_id: RequestId,
    now: datetime,
) -> UserEvent:
    return UserEvent(
        event_id=_new_id("event"),
        event_type=event_type,
        source=EventSource.ORKAFIN,
        app_id=context.app.app_id,
        actor_user_id=context.identity.user_id,
        workspace=context.workspace,
        metadata=metadata,
        occurred_at=now,
        received_at=now,
        request_id=request_id,
        correlation_id=CorrelationId(root=request_id.root),
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}:{uuid4()}"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
