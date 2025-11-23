import os
from app.llm_rag import rag_pipeline
from app.llm_rag.rag_pipeline import answer_query
from app.llm_rag.embeddings import build_vector_store

def setup_vector_store():
    # Build a tiny in-memory vector store for deterministic tests
    chunks = [
        {"id": "c1", "content": "year=2023 value=123", "start_row": 0, "end_row": 0},
        {"id": "c2", "content": "year=2024 value=130", "start_row": 1, "end_row": 1},
    ]
    store = build_vector_store(chunks)
    # Inject global
    rag_pipeline._VECTOR_STORE = store  # type: ignore

def test_llm_stub_answer(monkeypatch):
    setup_vector_store()
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_STUB_ANSWER", "Stubbed contextual answer.")
    res = answer_query("What is 2023 value?")
    assert res.answer.startswith("Stubbed contextual answer")
    assert res.failure_mode is None
    assert res.citations

def test_llm_disabled_fallback(monkeypatch):
    setup_vector_store()
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    monkeypatch.delenv("LLM_STUB_ANSWER", raising=False)
    res = answer_query("What is 2024 value?")
    assert "Grounded answer" in res.answer
    assert res.failure_mode is None
    assert res.citations