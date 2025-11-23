import os
from typing import List

# Optional OpenAI client import
try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

SAFE_MAX_TOKENS = 512

SYSTEM_PROMPT = (
    "You are a citation-grounded assistant. Use ONLY the provided context. "
    "If the answer is not fully supported by the context, ask for clarification succinctly. "
    "Return concise factual sentences; avoid speculation."  # No role-play
)

def _truncate(text: str, max_len: int = 2000) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."

def build_prompt(context_chunks: List[str], query: str) -> str:
    context_block = "\n---\n".join(f"Chunk {i+1}:\n{_truncate(c)}" for i, c in enumerate(context_chunks))
    prompt = (
        f"{SYSTEM_PROMPT}\n\nContext:\n{context_block}\n\nUser Query: {query}\n\nAnswer:"
    )
    return prompt

def generate_llm_answer(context_chunks: List[str], query: str) -> str | None:
    enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
    provider = os.getenv("LLM_PROVIDER", "openai")
    # Deterministic stub for tests/eval without external API dependency.
    stub = os.getenv("LLM_STUB_ANSWER")
    if enabled and stub:
        return stub.strip()
    if not enabled:
        return None
    if provider != "openai" or OpenAI is None:
        return None
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    if not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key)
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        prompt = build_prompt(context_chunks, query)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=SAFE_MAX_TOKENS,
            temperature=0.0,
        )
        answer = resp.choices[0].message.content.strip()
        # Basic safety: ensure at least one token from context appears; else fallback
        joined = " ".join(context_chunks)
        tokens = set(t.lower() for t in joined.split())
        answer_tokens = set(a.lower() for a in answer.split())
        overlap = tokens.intersection(answer_tokens)
        if not overlap:
            return None
        # Remove any leading phrases like "Based on the context" to keep concise
        return answer.replace("Based on the context,", "").strip()
    except Exception:
        return None
