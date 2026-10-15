from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentSummaryResponse(BaseModel):
    """Public metadata for a document the current user may read."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    source_name: str
    content_type: str
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


class DocumentChunkResponse(BaseModel):
    """A readable text chunk belonging to an authorized document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chunk_index: int
    content: str
    created_at: datetime


class DocumentDetailResponse(DocumentSummaryResponse):
    """Document metadata plus its readable text chunks."""

    chunks: list[DocumentChunkResponse]
