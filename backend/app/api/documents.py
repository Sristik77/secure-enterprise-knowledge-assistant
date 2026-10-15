from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import (
    Document,
    DocumentPermission,
    User,
    UserRole,
)
from app.services.document_access import readable_document_filter
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentSummaryResponse,
)


router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("", response_model=list[DocumentSummaryResponse])
def list_readable_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    """List only documents the authenticated user is allowed to read."""
    statement = (
        select(Document)
        .where(readable_document_filter(current_user.id))
        .order_by(Document.created_at.desc(), Document.id)
    )

    return list(db.scalars(statement).all())


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
)
def read_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    """Return document content only after checking read permissions."""
    statement = (
        select(Document)
        .options(selectinload(Document.chunks))
        .where(
            Document.id == document_id,
            readable_document_filter(current_user.id),
        )
    )

    document = db.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return document
