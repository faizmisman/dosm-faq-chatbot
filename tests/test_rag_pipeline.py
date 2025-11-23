from app.llm_rag import rag_pipeline
from app.llm_rag.rag_pipeline import answer_query
from app.llm_rag.embeddings import VectorStoreWrapper
import os
from unittest.mock import MagicMock, patch

def test_rag_refusal_without_dataset():
    os.environ.pop("DATASET_PATH", None)
    rag_pipeline._VECTOR_STORE = None  # reset global
    rr = answer_query("What is CPI 2023?")
    assert rr.failure_mode is not None
    # confidence may be >0 due to vector distances normalization; ensure below threshold
    assert rr.confidence < 0.25

def test_rag_answer_with_dataset(tmp_path, mock_database_operations):
    # Mock the vector store to return pre-defined search results
    mock_store = MagicMock(spec=VectorStoreWrapper)
    mock_store.search.return_value = [
        ({"id": "c1", "content": "year=2023 value=123", "start_row": 0, "end_row": 0}, 0.9)
    ]
    
    # Inject mock store directly
    rag_pipeline._VECTOR_STORE = mock_store
    
    rr = answer_query("2023 123")
    assert rr.failure_mode is None
    assert rr.confidence > 0.0
    assert rr.citations
