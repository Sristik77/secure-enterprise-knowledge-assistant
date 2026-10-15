"""Permission-aware semantic retrieval over document chunks."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.document_access import readable_document_filter
from app.models import Document, DocumentChunk
from app.services.embeddings import (
    EMBEDDING_DIMENSIONS,
    EmbeddingError,
    embed_texts,
)


@dataclass(frozen=True)
class RetrievedChunk:
    """A relevant chunk from a document the user may read."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    source_name: str
    chunk_index: int
    content: str
    similarity: float


def search_chunks(
    db: Session,
    user_id: UUID,
    query: str,
    *,
    limit: int = 5,
    min_similarity: float = 0.0,
) -> list[RetrievedChunk]:
    """Find semantically similar chunks the user is authorized to read."""
    normalized_query = query.strip()

    if not normalized_query:
        raise ValueError("Search query must not be empty.")
    if not 1 <= limit <= 20:
        raise ValueError("Search limit must be between 1 and 20.")
    if not -1.0 <= min_similarity <= 1.0:
        raise ValueError("Minimum similarity must be between -1 and 1.")

    query_vectors = embed_texts([normalized_query])
    if len(query_vectors) != 1:
        raise EmbeddingError("The embedding service returned an invalid result.")

    query_vector = query_vectors[0]
    if len(query_vector) != EMBEDDING_DIMENSIONS:
        raise EmbeddingError("The query embedding has an invalid dimension.")

    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    similarity = 1.0 - distance

    statement = (
        select(
            DocumentChunk.id.label("chunk_id"),
            Document.id.label("document_id"),
            Document.title.label("document_title"),
            Document.source_name.label("source_name"),
            DocumentChunk.chunk_index.label("chunk_index"),
            DocumentChunk.content.label("content"),
            similarity.label("similarity"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            readable_document_filter(user_id),
            DocumentChunk.embedding.is_not(None),
            similarity >= min_similarity,
        )
        .order_by(distance.asc(), DocumentChunk.id.asc())
        .limit(limit)
    )

    rows = db.execute(statement).mappings().all()

    return [
        RetrievedChunk(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            document_title=row["document_title"],
            source_name=row["source_name"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            similarity=max(-1.0, min(1.0, float(row["similarity"]))),
        )
        for row in rows
    ]

