
"""Authenticated retrieval-augmented generation chat API."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Conversation, Message, User
from app.schemas.chat import ChatCitation, ChatRequest, ChatResponse
from app.services.embeddings import EmbeddingError
from app.services.llm import LLMError, generate_answer
from app.services.retrieval import search_chunks

router = APIRouter(prefix="/chat", tags=["Chat"])

NO_CONTEXT_ANSWER = (
    "I don't have enough information in the documents you can access "
    "to answer that question."
)


def _get_or_create_conversation(
    db: Session,
    conversation_id,
    user_id,
    question: str,
) -> Conversation:
    """Return an owned conversation or create a new one."""
    if conversation_id is not None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        conversation = db.scalar(statement)

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )

        return conversation

    conversation = Conversation(
        user_id=user_id,
        title=question[:60],
    )
    db.add(conversation)
    db.flush()
    return conversation


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """Answer a question and persist the exchange in its conversation."""
    try:
        conversation = _get_or_create_conversation(
            db=db,
            conversation_id=payload.conversation_id,
            user_id=current_user.id,
            question=payload.question,
        )

        # Retrieve only chunks the current user is authorized to access.
        chunks = search_chunks(
            db=db,
            user_id=current_user.id,
            query=payload.question,
            limit=payload.limit,
            min_similarity=payload.min_similarity,
        )

        if not chunks:
            answer = NO_CONTEXT_ANSWER
            citations = []
        else:
            context_parts = []

            for index, chunk in enumerate(chunks, start=1):
                context_parts.append(
                    f"[Source {index}]\n"
                    f"Document title: {chunk.document_title}\n"
                    f"Source name: {chunk.source_name}\n"
                    f"Chunk index: {chunk.chunk_index}\n"
                    f"Content:\n{chunk.content}"
                )

            context = "\n\n---\n\n".join(context_parts)

            answer = generate_answer(payload.question, context)

            citations = [
                ChatCitation(
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    source_name=chunk.source_name,
                    chunk_index=chunk.chunk_index,
                    similarity=chunk.similarity,
                )
                for chunk in chunks
            ]

        # Save the question and answer only after the exchange succeeds.
        db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=payload.question,
                citations=[],
            )
        )

        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                citations=[
                    citation.model_dump(mode="json")
                    for citation in citations
                ],
            )
        )

        # Update the conversation's last-activity timestamp.
        conversation.updated_at = datetime.now(timezone.utc)

        db.commit()

        return ChatResponse(
            question=payload.question,
            answer=answer,
            citations=citations,
            conversation_id=conversation.id,
        )

    except EmbeddingError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search is temporarily unavailable.",
        ) from None

    except LLMError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The answer service is temporarily unavailable.",
        ) from None

    except Exception:
        db.rollback()
        raise
