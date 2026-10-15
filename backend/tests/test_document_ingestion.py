from io import BytesIO

import pytest
from docx import Document as DocxDocument

from app.services.document_ingestion import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MAX_FILE_SIZE_BYTES,
    DocumentIngestionError,
    chunk_text,
    extract_text,
)


def create_docx(text: str) -> bytes:
    document = DocxDocument()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_extract_text_file():
    assert extract_text("notes.txt", b"Hello enterprise RAG!") == (
        "Hello enterprise RAG!"
    )


def test_extract_text_utf8_bom():
    assert extract_text("notes.txt", b"\xef\xbb\xbfHello") == "Hello"


def test_extract_text_docx():
    content = create_docx("DOCX extraction works.")
    assert extract_text("notes.docx", content) == "DOCX extraction works."


def test_reject_unsupported_extension():
    with pytest.raises(DocumentIngestionError):
        extract_text("notes.exe", b"some content")


def test_reject_empty_file():
    with pytest.raises(DocumentIngestionError):
        extract_text("notes.txt", b"")


def test_reject_whitespace_only_file():
    with pytest.raises(DocumentIngestionError):
        extract_text("notes.txt", b"   \n\t  ")


def test_reject_invalid_utf8():
    with pytest.raises(DocumentIngestionError):
        extract_text("notes.txt", b"\xff\xfe\xfa")


def test_reject_oversized_file():
    content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
    with pytest.raises(DocumentIngestionError):
        extract_text("notes.txt", content)


def test_reject_malformed_pdf():
    with pytest.raises(DocumentIngestionError):
        extract_text("broken.pdf", b"This is not a valid PDF.")


def test_chunk_text_normalizes_whitespace():
    assert chunk_text("  hello \n world\t again  ") == [
        "hello world again"
    ]


def test_chunk_text_preserves_overlap():
    result = chunk_text("abcdefghijklm", chunk_size=10, overlap=3)

    assert result == ["abcdefghij", "hijklm"]
    assert result[1].startswith(result[0][-3:])


def test_chunk_text_shorter_than_chunk_size():
    assert chunk_text("short", chunk_size=10, overlap=2) == ["short"]


def test_chunk_text_empty_input():
    assert chunk_text(" \n\t ") == []


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [
        (0, 0),
        (-1, 0),
        (10, -1),
        (10, 10),
        (10, 11),
    ],
)
def test_chunk_text_rejects_invalid_parameters(chunk_size, overlap):
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=chunk_size, overlap=overlap)


def test_default_chunk_settings_are_valid():
    assert CHUNK_SIZE > 0
    assert 0 <= CHUNK_OVERLAP < CHUNK_SIZE
