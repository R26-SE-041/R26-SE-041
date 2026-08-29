from dataclasses import fields

import app.agents.tutor.memory as tutor_memory
from app.agents.tutor.config import load_tutor_config, load_tutor_instructions
from app.agents.tutor.memory import (
    ALLOWED_MEMORY_FIELDS,
    TutorMemento,
    contextual_retrieval_query,
    filter_allowed_memory_fields,
    get_relevant_memento,
    update_memento,
)


def test_tutor_markdown_instructions_are_loaded():
    config = load_tutor_config()
    instructions = load_tutor_instructions()
    assert "retrieved RAG context" in config.skills
    assert "professional university study assistant" in config.persona
    assert config.skills in instructions
    assert config.persona in instructions


def test_memento_configuration_is_loaded_and_non_empty():
    config = load_tutor_config()
    assert config.memento
    assert "session-level context" in config.memento
    assert "Do not store passwords" in config.memento


def test_memory_schema_contains_only_allowed_fields():
    stored_fields = {field.name for field in fields(TutorMemento)} - {"updated_at"}
    assert stored_fields == ALLOWED_MEMORY_FIELDS


def test_sensitive_or_unknown_fields_are_filtered():
    filtered = filter_allowed_memory_fields(
        {
            "language": "english",
            "previous_question": "What is inversion of control?",
            "password": "must-not-be-stored",
            "api_key": "must-not-be-stored",
            "full_document": "must-not-be-stored",
        }
    )
    assert filtered == {
        "language": "english",
        "previous_question": "What is inversion of control?",
    }


def test_related_follow_up_uses_short_lived_memento_only():
    session_id = "test-related-follow-up"
    update_memento(
        session_id,
        language="english",
        document_ids=["document-1"],
        question="What is dependency injection?",
        answer="It supplies an object's dependencies from outside the object.",
    )

    memento = get_relevant_memento(session_id, "Can you explain it with an example?")

    assert memento is not None
    assert memento["language"] == "english"
    assert memento["document_ids"] == ["document-1"]
    assert "dependency injection" in memento["previous_question"]


def test_unrelated_question_does_not_receive_old_memento():
    session_id = "test-unrelated-question"
    update_memento(
        session_id,
        language="english",
        document_ids=["document-1"],
        question="What is dependency injection?",
        answer="It supplies an object's dependencies from outside the object.",
    )

    assert get_relevant_memento(session_id, "What is the difference between RAM and ROM?") is None


def test_follow_up_retrieval_keeps_previous_topic():
    memento = {"previous_question": "What are a dog's daily care needs?"}
    assert contextual_retrieval_query("Can you explain that more simply?", memento) == (
        "What are a dog's daily care needs? Can you explain that more simply?"
    )
    unrelated = "Which dog breeds are listed?"
    assert contextual_retrieval_query(unrelated, None) == unrelated


def test_expired_memento_is_removed(monkeypatch):
    session_id = "test-expired-memento"
    clock = iter((100.0, 100.0 + tutor_memory._TTL_SECONDS + 1))
    monkeypatch.setattr(tutor_memory.time, "monotonic", lambda: next(clock))
    update_memento(
        session_id,
        language="english",
        document_ids=["document-1"],
        question="What is dependency injection?",
        answer="Dependencies are supplied externally.",
    )

    assert get_relevant_memento(session_id, "Can you explain it again?") is None
    assert session_id not in tutor_memory._sessions
