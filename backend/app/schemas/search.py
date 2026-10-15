"""Request and response schemas for semantic document search."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SearchRequest(BaseModel):
    """Parameters for a permission-aware semantic search."""

    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.0, ge=-1.0, le=1.0)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Search query must not be blank.")
        return value


class SearchResultItem(BaseModel):
    """One matching document chunk."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    source_name: str
    chunk_index: int
    content: str
    similarity: float = Field(ge=-1.0, le=1.0)


class SearchResponse(BaseModel):
    """Results returned by semantic search."""

    query: str
    results: list[SearchResultItem]
    total: int
