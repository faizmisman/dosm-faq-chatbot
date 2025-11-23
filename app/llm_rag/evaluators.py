"""Offline evaluation harness.

Reads JSONL queries, invokes answer_query, computes simple metrics:
 - hit_rate (placeholder heuristic: any citation -> hit)
 - refusal_rate (failure_mode == 'refuse')
 - clarify_rate (failure_mode == 'clarify')
 - latency p50/p95 (ms)

Extend later with ground-truth labels & hallucination tests.
"""
import json, time, statistics, sys
from typing import Iterable, List, Dict, Any
from pathlib import Path
from app.llm_rag.rag_pipeline import answer_query

def run_eval(queries: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    latencies: List[int] = []
    refusals = 0
    clarifies = 0
    hits = 0
    results: List[Dict[str, Any]] = []
    t0 = time.time()
    for item in queries:
        q = item.get("query")
        if not q:
            continue
        q_start = time.time()
        rr = answer_query(q)
        latency_ms = int((time.time() - q_start) * 1000)
        latencies.append(latency_ms)
        if rr.failure_mode == "refuse":
            refusals += 1
        elif rr.failure_mode == "clarify":
            clarifies += 1
        else:
            # Treat any citation as a retrieval hit for now
            if rr.citations:
                hits += 1
        results.append({
            "id": item.get("id"),
            "query": q,
            "answer": rr.answer,
            "failure_mode": rr.failure_mode,
            "confidence": rr.confidence,
            "citations": rr.citations,
            "latency_ms": latency_ms
        })
    elapsed_s = time.time() - t0
    count = len(results)
    p50 = statistics.median(latencies) if latencies else 0
    p95 = int(statistics.quantiles(latencies, n=100)[94]) if len(latencies) >= 20 else max(latencies) if latencies else 0
    summary = {
        "count": count,
        "elapsed_s": elapsed_s,
        "hit_rate": hits / count if count else 0.0,
        "refusal_rate": refusals / count if count else 0.0,
        "clarify_rate": clarifies / count if count else 0.0,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
    }
    return {"summary": summary, "results": results}

def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out

def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: python -m app.llm_rag.evaluators <queries.jsonl> [--out results.json]")
        return 2
    infile = argv[1]
    outfile = None
    if "--out" in argv:
        idx = argv.index("--out")
        if idx + 1 < len(argv):
            outfile = argv[idx + 1]
    queries = _load_jsonl(infile)
    report = run_eval(queries)
    out_json = json.dumps(report, indent=2)
    if outfile:
        Path(outfile).write_text(out_json, encoding="utf-8")
        print(f"Wrote results to {outfile}")
    else:
        print(out_json)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
