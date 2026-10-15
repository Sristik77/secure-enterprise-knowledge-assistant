from types import SimpleNamespace

import pytest

from app.services import backfill_embeddings


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, chunks):
        self.chunks = chunks
        self.commit_count = 0
        self.rollback_count = 0
        self.closed = False

    def scalars(self, statement):
        missing = [
            chunk for chunk in self.chunks if chunk.embedding is None
        ]
        return FakeResult(missing[: statement._limit_clause.value])

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True


def make_chunks(count):
    return [
        SimpleNamespace(
            content=f"Document chunk {i}",
            embedding=None,
            document_id="document-1",
            chunk_index=i,
        )
        for i in range(count)
    ]


def test_backfill_updates_chunks_in_batches(monkeypatch):
    chunks = make_chunks(3)
    session = FakeSession(chunks)
    calls = []

    def fake_embed_texts(texts):
        calls.append(list(texts))
        return [[0.1] * 384 for _ in texts]

    monkeypatch.setattr(
        backfill_embeddings, "embed_texts", fake_embed_texts
    )

    updated = backfill_embeddings.backfill_missing_embeddings(
        session, batch_size=2
    )

    assert updated == 3
    assert len(calls) == 2
    assert session.commit_count == 2
    assert session.rollback_count == 0
    assert all(len(chunk.embedding) == 384 for chunk in chunks)


def test_backfill_rolls_back_when_embedding_fails(monkeypatch):
    session = FakeSession(make_chunks(1))

    def fail_embedding(texts):
        raise backfill_embeddings.EmbeddingError("Simulated failure")

    monkeypatch.setattr(
        backfill_embeddings, "embed_texts", fail_embedding
    )

    with pytest.raises(backfill_embeddings.EmbeddingError):
        backfill_embeddings.backfill_missing_embeddings(session)

    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_backfill_rejects_invalid_batch_size():
    session = FakeSession([])

    with pytest.raises(ValueError, match="batch_size"):
        backfill_embeddings.backfill_missing_embeddings(
            session, batch_size=0
        )


def test_backfill_rejects_unexpected_embedding_count(monkeypatch):
    session = FakeSession(make_chunks(2))

    monkeypatch.setattr(
        backfill_embeddings,
        "embed_texts",
        lambda texts: [[0.1] * 384],
    )

    with pytest.raises(backfill_embeddings.EmbeddingError):
        backfill_embeddings.backfill_missing_embeddings(session)

    assert session.commit_count == 0
    assert session.rollback_count == 1
