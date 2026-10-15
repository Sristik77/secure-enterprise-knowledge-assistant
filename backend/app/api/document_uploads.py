from pathlib import PurePath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Document, DocumentChunk, User
from app.schemas.documents import DocumentDetailResponse
from app.services.document_ingestion import (
    MAX_FILE_SIZE_BYTES,
    DocumentIngestionError,
    chunk_text,
    extract_text,
)

router = APIRouter(prefix="/documents", tags=["Documents"])

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
}


@router.post(
    "",
    response_model=DocumentDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=300),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    """Extract, chunk, and store an authenticated user's document."""

    original_name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]

    if not original_name or original_name in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid filename is required.",
        )

    extension = PurePath(original_name).suffix.lower()

    if extension not in CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PDF, TXT, or DOCX file.",
        )

    try:
        # Read at most one byte beyond the limit to detect oversized uploads.
        content = await file.read(MAX_FILE_SIZE_BYTES + 1)

        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds the maximum allowed size of 10 MB.",
            )

        extracted_text = extract_text(original_name, content)
        chunks = chunk_text(extracted_text)

        if not chunks:
            raise DocumentIngestionError(
                "No readable text was found in the uploaded document."
            )

        document = Document(
            id=uuid4(),
            title=(title or "").strip() or PurePath(original_name).stem,
            source_name=original_name[:500],
            content_type=CONTENT_TYPES[extension],
            owner_id=current_user.id,
            metadata_json={
                "original_extension": extension,
                "chunk_count": len(chunks),
            },
        )

        document.chunks = [
            DocumentChunk(chunk_index=index, content=chunk)
            for index, chunk in enumerate(chunks)
        ]

        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    except DocumentIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be saved.",
        ) from exc

    finally:
        await file.close()
