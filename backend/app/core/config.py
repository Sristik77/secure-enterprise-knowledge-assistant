from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Validated application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Secure Enterprise Knowledge Assistant"
    app_env: Literal["development", "test", "production"] = "development"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)

    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, ge=1, le=65535, validation_alias="DB_PORT")
    db_name: str = Field(
        default="secure_knowledge_assistant",
        validation_alias="DB_NAME",
    )
    db_user: str = Field(default="postgres", validation_alias="DB_USER")
    db_password: SecretStr = Field(validation_alias="DB_PASSWORD")
    jwt_secret_key: SecretStr = Field(validation_alias="JWT_SECRET_KEY")
    jwt_algorithm: Literal["HS256"] = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings for the running application."""
    return Settings()
