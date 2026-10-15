from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Secure enterprise knowledge assistant with "
            "permission-aware document retrieval."
        ),
    )

    @application.get("/health/live", tags=["Health"])
    def health_live() -> dict[str, str]:
        """Report whether the API process is running."""
        return {"status": "ok"}

    application.include_router(auth_router)
    application.include_router(admin_router)

    return application


app = create_app()
