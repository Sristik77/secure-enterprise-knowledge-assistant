import uuid
from typing import Any

import pytest
from fastapi import HTTPException

from app.api.deps import require_roles
from app.models import User


class FakeRoleSession:
    """Minimal session substitute for RBAC dependency tests."""

    def __init__(self, has_role: bool) -> None:
        self.has_role = has_role

    def scalar(self, statement: Any) -> uuid.UUID | None:
        if self.has_role:
            return uuid.uuid4()
        return None


def make_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="employee@example.com",
        password_hash="test-hash",
        full_name="Test Employee",
        is_active=True,
    )


def test_require_roles_allows_user_with_required_role() -> None:
    user = make_user()
    checker = require_roles("admin")

    result = checker(
        current_user=user,
        db=FakeRoleSession(has_role=True),
    )

    assert result is user


def test_require_roles_rejects_user_without_required_role() -> None:
    user = make_user()
    checker = require_roles("admin")

    with pytest.raises(HTTPException) as exc_info:
        checker(
            current_user=user,
            db=FakeRoleSession(has_role=False),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "You do not have the required role."


def test_require_roles_accepts_multiple_allowed_roles() -> None:
    user = make_user()
    checker = require_roles("admin", "knowledge_manager")

    result = checker(
        current_user=user,
        db=FakeRoleSession(has_role=True),
    )

    assert result is user


def test_require_roles_rejects_empty_role_configuration() -> None:
    with pytest.raises(ValueError):
        require_roles()

    with pytest.raises(ValueError):
        require_roles(" ", "")
