from io import BytesIO
from pathlib import PurePath

from docx import Document as DocxDocument
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


class DocumentIngestionError(ValueError):
    """Raised when an uploaded document cannot be processed."""


def extract_text(filename: str, content: bytes) -> str:
    """Extract text from a supported document, with a 10 MB size limit."""
    extension = PurePath(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentIngestionError(
            "Unsupported file type. Upload a PDF, TXT, or DOCX file."
        )

    if not content:
        raise DocumentIngestionError("The uploaded file is empty.")

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise DocumentIngestionError(
            "File exceeds the maximum allowed size of 10 MB."
        )

    try:
        if extension == ".txt":
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise DocumentIngestionError(
                    "TXT files must use UTF-8 encoding."
                ) from exc

        elif extension == ".pdf":
            reader = PdfReader(BytesIO(content), strict=True)

            if reader.is_encrypted:
                raise DocumentIngestionError(
                    "Password-protected PDFs are not supported."
                )

            text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )

        else:
            document = DocxDocument(BytesIO(content))
            text = "\n".join(
                paragraph.text for paragraph in document.paragraphs
            )

    except DocumentIngestionError:
        raise
    except Exception as exc:
        raise DocumentIngestionError(
            "The file could not be read. Check that it is a valid document."
        ) from exc

    text = text.replace("\x00", "").strip()

    if not text:
        raise DocumentIngestionError(
            "No readable text was found in the uploaded document."
        )

    return text


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks for later retrieval."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between zero and chunk_size - 1.")

    normalized = " ".join(text.split())

    if not normalized:
        return []

    chunks = []
    start = 0

    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunk = normalized[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == len(normalized):
            break

        start = end - overlap

    return chunks
