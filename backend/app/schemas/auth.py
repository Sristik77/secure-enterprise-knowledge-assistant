
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from uuid import UUID


class RegisterRequest(BaseModel):
    """Validated input for creating a user account."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        """Normalize email addresses for consistent account lookup."""
        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Reject names that are empty after trimming."""
        value = value.strip()
        if not value:
            raise ValueError("Full name cannot be empty")
        return value


class LoginRequest(BaseModel):
    """Validated input for logging in."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class UserResponse(BaseModel):
    """Public user details; never includes password hashes."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool


class TokenResponse(BaseModel):
    """Access-token response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"
