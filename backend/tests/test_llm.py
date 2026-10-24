from types import SimpleNamespace

import pytest
from openai import APIConnectionError

from app.services import llm


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(
            completions=completions
        )


def make_response(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content)
            )
        ]
    )


@pytest.fixture(autouse=True)
def reset_llm_client_cache():
    llm.get_llm_client.cache_clear()
    yield
    llm.get_llm_client.cache_clear()


def test_generate_answer_uses_mocked_client(monkeypatch):
    completions = FakeCompletions(
        response=make_response("The policy allows access.")
    )
    monkeypatch.setattr(
        llm,
        "get_llm_client",
        lambda: FakeClient(completions),
    )

    answer = llm.generate_answer(
        "What does the policy allow?",
        "Document: Access Policy\nEmployees may access approved systems.",
    )

    assert answer == "The policy allows access."
    assert completions.kwargs["model"] == llm.get_settings().groq_model
    assert completions.kwargs["messages"][0]["role"] == "system"
    assert "Employees may access approved systems." in (
        completions.kwargs["messages"][1]["content"]
    )


@pytest.mark.parametrize(
    ("question", "context"),
    [
        ("", "Some document text"),
        ("   ", "Some document text"),
        ("A question", ""),
        ("A question", "   "),
    ],
)
def test_generate_answer_rejects_empty_input(question, context):
    with pytest.raises(ValueError):
        llm.generate_answer(question, context)


def test_generate_answer_requires_api_key(monkeypatch):
    settings = llm.get_settings()
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: settings.model_copy(update={"groq_api_key": None}),
    )

    with pytest.raises(llm.LLMError, match="not configured"):
        llm.generate_answer("A question", "Some context")


def test_generate_answer_handles_connection_error(monkeypatch):
    completions = FakeCompletions(
        error=APIConnectionError(request=None)
    )
    monkeypatch.setattr(
        llm,
        "get_llm_client",
        lambda: FakeClient(completions),
    )

    with pytest.raises(llm.LLMError, match="could not be reached"):
        llm.generate_answer("A question", "Some context")


def test_generate_answer_rejects_empty_model_response(monkeypatch):
    completions = FakeCompletions(response=make_response("  "))
    monkeypatch.setattr(
        llm,
        "get_llm_client",
        lambda: FakeClient(completions),
    )

    with pytest.raises(llm.LLMError, match="empty answer"):
        llm.generate_answer("A question", "Some context")