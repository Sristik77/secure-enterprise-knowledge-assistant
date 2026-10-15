"""Backfill missing document chunk embeddings in committed batches."""

import argparse
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import DocumentChunk
from app.services.embeddings import EmbeddingError, embed_texts

logger = logging.getLogger(__name__)


def backfill_missing_embeddings(
    session: Session, batch_size: int = 100
) -> int:
    """Generate and persist vectors for chunks without embeddings."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    updated = 0

    while True:
        chunks = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.embedding.is_(None))
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).all()

        if not chunks:
            return updated

        try:
            vectors = embed_texts([chunk.content for chunk in chunks])

            if len(vectors) != len(chunks):
                raise EmbeddingError(
                    "The embedding service returned an unexpected "
                    "number of vectors."
                )

            for chunk, vector in zip(chunks, vectors):
                chunk.embedding = vector

            session.commit()
            updated += len(chunks)

        except Exception:
            session.rollback()
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    session = SessionLocal()

    try:
        count = backfill_missing_embeddings(session, args.batch_size)
        logger.info("Backfilled %d document chunks.", count)
        return 0
    except Exception:
        logger.exception(
            "Embedding backfill failed; the current batch was rolled back."
        )
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
