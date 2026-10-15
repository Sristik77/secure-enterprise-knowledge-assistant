"""Shared document access-control query helpers."""

from uuid import UUID

from sqlalchemy import or_, select

from app.models import Document, DocumentPermission, UserRole


def readable_document_filter(user_id: UUID):
    """Match documents owned by a user or readable through any assigned role."""
    role_permission = (
        select(DocumentPermission.id)
        .join(
            UserRole,
            UserRole.role_id == DocumentPermission.role_id,
        )
        .where(
            DocumentPermission.document_id == Document.id,
            DocumentPermission.can_read.is_(True),
            UserRole.user_id == user_id,
        )
        .exists()
    )

    return or_(
        Document.owner_id == user_id,
        role_permission,
    )
