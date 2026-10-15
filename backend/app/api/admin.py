from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import User
from app.schemas.auth import UserResponse


router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/users", response_model=list[UserResponse])
def list_users(
    _admin: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> list[User]:
    """List user accounts; accessible only to users with the admin role."""
    statement = select(User).order_by(User.email)
    return list(db.scalars(statement).all())
