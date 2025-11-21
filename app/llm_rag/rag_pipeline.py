from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import os
from .chunking import load_dataset, build_chunks
from .embeddings import build_vector_store, VectorStoreWrapper

_VECTOR_STORE: VectorStoreWrapper | None = None
_CONF_THRESHOLD = 0.25

@dataclass
class RagResult:
    answer: str
    citations: List[dict]
    confidence: float
    failure_mode: Optional[str] = None

def _init_store_if_needed():
    global _VECTOR_STORE
    if _VECTOR_STORE is not None:
        return
    path = os.getenv("DATASET_PATH")
    if not path or not os.path.exists(path):
        return
    try:
        df = load_dataset(path)
        # Ensure at least one chunk even for tiny datasets
        chunks = build_chunks(df, chunk_size=max(1, min(len(df), 25)))
        _VECTOR_STORE = build_vector_store(chunks)
    except Exception:
        _VECTOR_STORE = None

def answer_query(query: str, user_context: Dict[str, Any] | None = None) -> RagResult:
    _init_store_if_needed()
    if _VECTOR_STORE is None:
        return RagResult(
            answer="Data not ingested yet. Please set DATASET_PATH and build vector store.",
            citations=[],
            confidence=0.0,
            failure_mode="low_confidence"
        )
    results = _VECTOR_STORE.search(query, k=5)
    if not results:
        return RagResult(
            answer="No relevant data found.",
            citations=[],
            confidence=0.0,
            failure_mode="low_confidence"
        )
    top_chunk, top_score = results[0]
    confidence = float(top_score)
    # Adjust confidence scaling if scores exceed 1 (Chroma may return distance-based metrics)
    if confidence > 1.0:
        confidence = 1.0 / confidence  # invert large distances
    if confidence < _CONF_THRESHOLD:
        return RagResult(
            answer="I cannot confidently answer from the dataset; could you clarify or provide more specifics?",
            citations=[],
            confidence=confidence,
            failure_mode="clarify"
        )
    citations = [{
        "source": os.getenv("DATASET_SOURCE_URL", "dosm_dataset"),
        "snippet": top_chunk["content"][:200],
        "page_or_row": top_chunk["start_row"]
    }]
    answer = f"Based on dataset rows {top_chunk['start_row']}–{top_chunk['end_row']}, key info: {top_chunk['content'][:180]}"
    return RagResult(
        answer=answer,
        citations=citations,
        confidence=confidence,
        failure_mode=None
    )
