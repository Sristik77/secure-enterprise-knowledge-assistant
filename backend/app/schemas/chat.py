
"""Request and response schemas for RAG chat."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Question and retrieval settings for a chat request."""

    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=10)
    min_similarity: float = Field(default=0.0, ge=-1.0, le=1.0)
    conversation_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be blank.")
        return value


class ChatCitation(BaseModel):
    """A retrieved source used to generate the answer."""

    document_id: UUID
    document_title: str
    source_name: str
    chunk_index: int
    similarity: float = Field(ge=-1.0, le=1.0)


class ChatResponse(BaseModel):
    """Grounded answer and its supporting sources."""

    question: str
    answer: str
    citations: list[ChatCitation]
    conversation_id: UUID | None = None
