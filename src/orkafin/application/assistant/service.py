"""Compose verified context, retrieval, generation, and local conversations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from orkafin.application.context import TrustedContextResolutionService
from orkafin.application.response_generation import (
    ResponseGenerationRequest,
    ResponseGenerationService,
)
from orkafin.application.retrieval import (
    DeterministicRetrievalService,
    RetrievalRequest,
    normalize_question,
)
from orkafin.application.retrieval.models import RetrievalResult
from orkafin.core.errors import DomainError
from orkafin.domain.base import DataOwner, DomainModel, Identifier, ShortText
from orkafin.domain.catalog import VerificationStatus
from orkafin.domain.context import ClientContextHint, ResolvedPageContext
from orkafin.domain.conversations import Conversation, ConversationStatus, Message, MessageRole
from orkafin.domain.identifiers import Permission, RequestId, SafeReference
from orkafin.domain.responses import AssistantResponse
from orkafin.domain.sources import RetrievedSource, SourceType
from orkafin.infrastructure.database.repositories import OrkaFinRepository
from orkafin.infrastructure.database.session import Database
from orkafin.providers.contracts import ResponseIntent
from orkafin.providers.history import ConversationHistoryEntry, HistoryInputRole


class AssistantQuery(DomainModel):
    """Bounded public query input; all identity and context fields remain hints."""

    question: ShortText
    context: ClientContextHint
    conversation_id: Identifier | None = None


class ConversationAccessError(DomainError):
    """Avoid disclosing whether another user's conversation exists."""

    status_code = 404
    public_message = "The requested conversation is unavailable."


class AssistantQueryService:
    """The only V1 service that writes user-visible assistant conversations."""

    def __init__(
        self,
        *,
        database: Database,
        context_service: TrustedContextResolutionService,
        retrieval_service: DeterministicRetrievalService,
        response_service: ResponseGenerationService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._context_service = context_service
        self._retrieval_service = retrieval_service
        self._response_service = response_service
        self._clock = clock or (lambda: datetime.now(UTC))

    async def query(self, value: AssistantQuery, *, request_id: RequestId) -> AssistantResponse:
        """Answer one request after context, ownership, retrieval, and output checks."""
        context = await self._context_service.resolve(
            client_hint=value.context,
            request_id=request_id,
            include_candidate_summary=_asks_for_candidate_summary(value.question),
        )
        conversation, history = self._load_or_create_conversation(
            supplied_id=value.conversation_id, context=context
        )
        user_message_at = self._clock()
        intent = _intent_for(value.question, context)
        retrieval = self._retrieve(value.question, context)
        if intent is ResponseIntent.CANDIDATE_SUMMARY:
            retrieval = _with_candidate_summary_source(retrieval, context)
        response = self._response_service.generate(
            ResponseGenerationRequest(
                user_question=value.question,
                context=context,
                retrieval=retrieval,
                intent=intent,
                response_id=_new_id("response"),
                conversation_id=conversation.conversation_id,
                conversation_history=history,
            )
        )
        self._persist_turn(
            conversation=conversation,
            question=value.question,
            user_message_at=user_message_at,
            response=response,
        )
        return response

    def get_conversation(
        self, *, conversation_id: str, context: ResolvedPageContext
    ) -> tuple[Conversation, tuple[Message, ...]]:
        """Return only a conversation owned by the verified user and workspace."""
        with self._database.session_factory() as session:
            repository = OrkaFinRepository(session)
            conversation = repository.get_conversation(conversation_id)
            if not _is_owned(conversation, context):
                raise ConversationAccessError
            assert conversation is not None
            return conversation, tuple(repository.list_messages(conversation_id))

    def _load_or_create_conversation(
        self, *, supplied_id: str | None, context: ResolvedPageContext
    ) -> tuple[Conversation, tuple[ConversationHistoryEntry, ...]]:
        with self._database.session_factory.begin() as session:
            repository = OrkaFinRepository(session)
            if supplied_id is not None:
                conversation = repository.get_conversation(supplied_id)
                if not _is_owned(conversation, context):
                    raise ConversationAccessError
                assert conversation is not None
                return conversation, _history_for(repository.list_messages(supplied_id))
            now = self._clock()
            conversation = Conversation(
                conversation_id=_new_id("conversation"),
                owner_user_id=context.identity.user_id,
                workspace=context.workspace,
                title="Assistant conversation",
                status=ConversationStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            repository.add_conversation(conversation)
            return conversation, ()

    def _retrieve(self, question: str, context: ResolvedPageContext) -> RetrievalResult:
        return self._retrieval_service.retrieve(
            RetrievalRequest(
                normalized_question=normalize_question(question),
                context=context,
                trusted_permissions=context.permissions,
                selected_entity_type=(
                    context.selected_entity.entity_type
                    if context.selected_entity is not None
                    else None
                ),
            )
        )

    def _persist_turn(
        self,
        *,
        conversation: Conversation,
        question: str,
        user_message_at: datetime,
        response: AssistantResponse,
    ) -> None:
        """Persist user-visible messages, excluding request-scoped candidate values."""
        assistant_content = (
            "An authorized candidate summary was provided for this request."
            if response.content.kind == "verified_fact"
            and any(
                source.source_type is SourceType.CANDIDATE_SUMMARY for source in response.sources
            )
            else response.content.text
        )
        source_ids = tuple(source.source_id for source in response.sources)
        with self._database.session_factory.begin() as session:
            repository = OrkaFinRepository(session)
            repository.add_message(
                Message(
                    message_id=_new_id("message"),
                    conversation_id=conversation.conversation_id,
                    role=MessageRole.USER,
                    content=question,
                    request_id=response.request_id,
                    created_at=user_message_at,
                )
            )
            repository.add_message(
                Message(
                    message_id=_new_id("message"),
                    conversation_id=conversation.conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=assistant_content,
                    source_ids=source_ids,
                    request_id=response.request_id,
                    created_at=response.created_at,
                )
            )
            repository.update_conversation(
                conversation.model_copy(update={"updated_at": response.created_at})
            )


def _intent_for(question: str, context: ResolvedPageContext) -> ResponseIntent:
    normalized = normalize_question(question)
    if context.candidate_summary is not None and _asks_for_candidate_summary(question):
        return ResponseIntent.CANDIDATE_SUMMARY
    if any(term in normalized for term in ("step by step", "how do i", "how to", "walk me")):
        return ResponseIntent.STEP_BY_STEP_HELP
    if any(
        term in normalized
        for term in ("explain this page", "this page", "explain page", "what can i do")
    ):
        return ResponseIntent.EXPLAIN_PAGE
    return ResponseIntent.EXPLAIN_PAGE


def _asks_for_candidate_summary(question: str) -> bool:
    normalized = normalize_question(question)
    return any(
        term in normalized
        for term in (
            "candidate summary",
            "summarize candidate",
            "summarize this candidate",
            "candidate details",
        )
    )


def _with_candidate_summary_source(
    retrieval: RetrievalResult, context: ResolvedPageContext
) -> RetrievalResult:
    summary = context.candidate_summary
    if summary is None:
        return retrieval
    source = RetrievedSource(
        source_id=summary.source_adapter_response_id,
        source_type=SourceType.CANDIDATE_SUMMARY,
        source_owner=DataOwner.ORKA_ATS,
        app_id=context.app.app_id,
        content_version=context.app.app_version,
        revision="adapter-v1",
        title="Authorized candidate summary",
        safe_reference=SafeReference(root=f"adapter://{context.app.app_id}/candidate-summary"),
        excerpt="Permission-filtered candidate summary returned by the owning application.",
        verification_status=VerificationStatus.VERIFIED,
        relevance_score=1.0,
        relevance_reason="Selected candidate summary verified by the owning application",
        required_permissions=(Permission(root="candidate.view"),),
        retrieved_at=summary.retrieved_at,
    )
    return retrieval.model_copy(
        update={"sources": (source, *retrieval.sources), "no_source_reason": None}
    )


def _history_for(messages: Sequence[Message]) -> tuple[ConversationHistoryEntry, ...]:
    return tuple(
        ConversationHistoryEntry(
            role=(
                HistoryInputRole.USER
                if message.role is MessageRole.USER
                else HistoryInputRole.ASSISTANT
            ),
            content=message.content,
        )
        for message in messages
    )


def _is_owned(conversation: Conversation | None, context: ResolvedPageContext) -> bool:
    return bool(
        conversation
        and conversation.owner_user_id == context.identity.user_id
        and conversation.workspace.workspace_id == context.workspace.workspace_id
        and conversation.workspace.app_id == context.workspace.app_id
    )


def _new_id(prefix: str) -> str:
    return f"{prefix}:{uuid4()}"
