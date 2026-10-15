"""Authenticated semantic document search API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.embeddings import EmbeddingError
from app.services.retrieval import search_chunks

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("", response_model=SearchResponse)
def semantic_search(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    """Search relevant chunks without exposing unauthorized documents."""
    try:
        chunks = search_chunks(
            db=db,
            user_id=current_user.id,
            query=payload.query,
            limit=payload.limit,
            min_similarity=payload.min_similarity,
        )
    except EmbeddingError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search is temporarily unavailable.",
        ) from None

    results = [
        SearchResultItem(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            source_name=chunk.source_name,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            similarity=chunk.similarity,
        )
        for chunk in chunks
    ]

    return SearchResponse(
        query=payload.query,
        results=results,
        total=len(results),
    )
