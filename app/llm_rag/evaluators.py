# Offline evaluation helpers (skeleton)
import json, time
from typing import Iterable

def run_eval(queries: Iterable[str]) -> dict:
    # Replace with real calls to answer_query and compute metrics
    t0 = time.time()
    results = [{"query": q, "decision": "refuse"} for q in queries]
    return {"count": len(results), "elapsed_s": time.time() - t0}
