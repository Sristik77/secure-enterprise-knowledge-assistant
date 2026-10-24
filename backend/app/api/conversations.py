
"""Authenticated conversation history endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models import Conversation, User
from app.schemas.conversations import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
)

router = APIRouter(prefix="/conversations", tags=["Conversation history"])


def _owned_conversation(
    db: Session, conversation_id: UUID, user_id: UUID
) -> Conversation:
    statement = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        .options(selectinload(Conversation.messages))
    )
    conversation = db.scalar(statement)
    if conversation is None:
        # Do not reveal whether another user's conversation exists.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conversation


@router.post(
    "",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    conversation = Conversation(
        user_id=current_user.id,
        title=payload.title.strip() or "New conversation",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Conversation]:
    statement = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    )
    return list(db.scalars(statement).all())


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Conversation:
    return _owned_conversation(db, conversation_id, current_user.id)
