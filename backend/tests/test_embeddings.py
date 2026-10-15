import numpy as np
import pytest

from app.services import embeddings


class FakeModel:
    def encode(self, texts, **kwargs):
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["convert_to_numpy"] is True
        return np.full((len(texts), 384), 0.5, dtype=np.float32)


def test_empty_input_does_not_load_model(monkeypatch):
    def fail_if_loaded():
        raise AssertionError("Model should not load for empty input")

    monkeypatch.setattr(embeddings, "_load_model", fail_if_loaded)

    assert embeddings.embed_texts([]) == []


def test_embed_texts_returns_one_384_dimension_vector_per_text(monkeypatch):
    monkeypatch.setattr(embeddings, "_load_model", lambda: FakeModel())

    result = embeddings.embed_texts(["First document chunk", "Second chunk"])

    assert len(result) == 2
    assert all(len(vector) == 384 for vector in result)
    assert all(isinstance(value, float) for vector in result for value in vector)


@pytest.mark.parametrize("texts", [[""], ["   "], ["valid text", "  "]])
def test_embed_texts_rejects_blank_text(texts):
    with pytest.raises(embeddings.EmbeddingError):
        embeddings.embed_texts(texts)


def test_embed_texts_wraps_model_loading_failure(monkeypatch):
    def fail_loading():
        raise RuntimeError("internal model error")

    monkeypatch.setattr(embeddings, "_load_model", fail_loading)

    with pytest.raises(embeddings.EmbeddingError):
        embeddings.embed_texts(["some text"])


def test_embed_texts_rejects_wrong_vector_dimensions(monkeypatch):
    class WrongDimensionModel:
        def encode(self, texts, **kwargs):
            return np.zeros((len(texts), 10), dtype=np.float32)

    monkeypatch.setattr(
        embeddings, "_load_model", lambda: WrongDimensionModel()
    )

    with pytest.raises(embeddings.EmbeddingError):
        embeddings.embed_texts(["some text"])


def test_embed_texts_rejects_non_finite_values(monkeypatch):
    class InvalidValueModel:
        def encode(self, texts, **kwargs):
            vectors = np.zeros((len(texts), 384), dtype=np.float32)
            vectors[0, 0] = np.nan
            return vectors

    monkeypatch.setattr(
        embeddings, "_load_model", lambda: InvalidValueModel()
    )

    with pytest.raises(embeddings.EmbeddingError):
        embeddings.embed_texts(["some text"])
