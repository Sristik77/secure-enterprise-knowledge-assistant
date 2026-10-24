from fastapi import FastAPI
from app.api.document_uploads import router as document_uploads_router
from app.api.admin import router as admin_router
from app.api.documents import router as documents_router
from app.api.auth import router as auth_router
from app.api.search import router as search_router
from app.core.config import get_settings
from app.api.chat import router as chat_router


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
    application.include_router(documents_router)
    application.include_router(document_uploads_router)
    application.include_router(search_router)
    application.include_router(chat_router)

    return application


app = create_app()
