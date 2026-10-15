"""Local text embedding generation for semantic document retrieval."""

from functools import lru_cache
from math import isfinite
from typing import Sequence

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384


class EmbeddingError(RuntimeError):
    """Raised when valid embeddings cannot be generated."""


@lru_cache(maxsize=1)
def _load_model():
    """Load and cache the embedding model on first use."""
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(MODEL_NAME, device="cpu")
    except Exception as exc:
        raise EmbeddingError(
            "The local embedding model could not be loaded."
        ) from exc


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Generate normalized, validated embeddings for a batch of texts."""
    if not texts:
        return []

    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise EmbeddingError("Embedding input must contain non-empty text.")

    try:
        model = _load_model()
        vectors = model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(
            "The local embedding model failed to generate embeddings."
        ) from exc

    try:
        if vectors.shape != (len(texts), EMBEDDING_DIMENSIONS):
            raise EmbeddingError("The embedding model returned an invalid shape.")

        result = vectors.tolist()

        for vector in result:
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise EmbeddingError("An embedding has an invalid dimension.")
            if not all(isfinite(float(value)) for value in vector):
                raise EmbeddingError("An embedding contains invalid numeric values.")

        return [[float(value) for value in vector] for vector in result]

    except EmbeddingError:
        raise
    except Exception as exc:
        raise EmbeddingError(
            "The embedding model returned an invalid result."
        ) from exc
