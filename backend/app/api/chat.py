"""Authenticated retrieval-augmented generation chat API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.chat import ChatCitation, ChatRequest, ChatResponse
from app.services.embeddings import EmbeddingError
from app.services.llm import LLMError, generate_answer
from app.services.retrieval import search_chunks

router = APIRouter(prefix="/chat", tags=["Chat"])

NO_CONTEXT_ANSWER = (
    "I don't have enough information in the documents you can access "
    "to answer that question."
)


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """Answer a question using only the user's authorized document chunks."""
    try:
        chunks = search_chunks(
            db=db,
            user_id=current_user.id,
            query=payload.question,
            limit=payload.limit,
            min_similarity=payload.min_similarity,
        )
    except EmbeddingError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search is temporarily unavailable.",
        ) from None

    if not chunks:
        return ChatResponse(
            question=payload.question,
            answer=NO_CONTEXT_ANSWER,
            citations=[],
        )

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

    try:
        answer = generate_answer(payload.question, context)
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The answer service is temporarily unavailable.",
        ) from None

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

    return ChatResponse(
        question=payload.question,
        answer=answer,
        citations=citations,
    )