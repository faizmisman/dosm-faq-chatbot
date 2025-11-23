from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import os
from .chunking import load_dataset, build_chunks
from .embeddings import build_vector_store, load_vector_store, VectorStoreWrapper
from .llm_provider import generate_llm_answer

_VECTOR_STORE: VectorStoreWrapper | None = None
_CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.25"))

def _normalize_score(raw: float) -> float:
    """Normalize raw similarity / distance to confidence in [0,1].
    Heuristics:
    - Negative scores -> clamp to small positive (0.05)
    - Scores > 1 treated as distance; invert (1/(1+raw))
    - Otherwise assume already relevance in [0,1]
    """
    if raw < 0:
        return 0.05
    if raw > 1.0:
        return 1.0 / (1.0 + raw)
    return raw

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
    # Try loading from PostgreSQL database first
    try:
        _VECTOR_STORE = load_vector_store()
        return
    except Exception:
        pass
    # Fallback: rebuild from dataset if available
    path = os.getenv("DATASET_PATH")
    if not path or not os.path.exists(path):
        return
    try:
        df = load_dataset(path)
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
    # Retrieve up to top-k chunks for potential multi-citation synthesis.
    k = int(os.getenv("RAG_TOP_K", "3"))
    results = _VECTOR_STORE.search(query, k=max(1, k))
    if not results:
        return RagResult(
            answer="No relevant data found.",
            citations=[],
            confidence=0.0,
            failure_mode="low_confidence"
        )
    top_chunk, top_score = results[0]
    confidence = _normalize_score(float(top_score))
    if confidence < _CONF_THRESHOLD:
        return RagResult(
            answer="I cannot confidently answer from the dataset; could you clarify or provide more specifics?",
            citations=[],
            confidence=confidence,
            failure_mode="clarify"
        )
    citations = []
    for chunk, score in results[:k]:
        snippet = (chunk.get("content") or "")[:160]
        citations.append({
            "source": os.getenv("DATASET_SOURCE_URL", "dosm_dataset"),
            "snippet": snippet,
            "page_or_row": chunk.get("start_row"),
            "confidence": _normalize_score(float(score))
        })

    # Simple template-based synthesis (Phase P2 without external LLM):
    content_chunks = [c[0]["content"] for c in results[:k]]
    content = "\n".join(content_chunks)
    # Extract simple key-value pairs of form key=value
    kv_pairs = []
    for line in content.splitlines():
        parts = [p.strip() for p in line.split()]  # naive tokenization
        for token in parts:
            if "=" in token:
                k,v = token.split("=",1)
                if k and v:
                    kv_pairs.append((k,v))
    summary_fragments = []
    seen = set()
    for k,v in kv_pairs[:6]:
        if k in seen: continue
        seen.add(k)
        summary_fragments.append(f"{k}={v}")
    summary_text = ", ".join(summary_fragments) if summary_fragments else content[:160]
    row_span = f"rows {top_chunk['start_row']}–{top_chunk['end_row']}" if top_chunk.get('start_row') is not None else "dataset snippet"
    llm_answer = generate_llm_answer(content_chunks, query)
    if llm_answer:
        answer = llm_answer
    else:
        answer = (
            f"Grounded answer ({row_span}): {summary_text}. "
            f"Query: '{query}'. Citations provided for transparency; no extrapolation beyond retrieved context."
        )
    return RagResult(
        answer=answer,
        citations=citations,
        confidence=confidence,
        failure_mode=None
    )
