from collections.abc import Callable
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Role, User, UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate a bearer token and return its active user."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        claims = decode_access_token(credentials.credentials)
        user_id = UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise unauthorized from None

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise unauthorized

    return user


def require_roles(*required_roles: str) -> Callable[..., User]:
    """Require an authenticated user to have at least one specified role."""
    normalized_roles = frozenset(
        role.strip().lower()
        for role in required_roles
        if role.strip()
    )

    if not normalized_roles:
        raise ValueError("At least one non-empty role name is required.")

    def role_checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role_id = db.scalar(
            select(Role.id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == current_user.id,
                Role.name.in_(normalized_roles),
            )
            .limit(1)
        )

        if role_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have the required role.",
            )

        return current_user

    return role_checker
