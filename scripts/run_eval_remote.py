#!/usr/bin/env python3
"""
Run evaluation against deployed /predict endpoint.
Usage: python scripts/run_eval_remote.py <endpoint_url> <api_key> <queries.jsonl> [--out results.json]
"""
import json
import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict, Any
import urllib.request
import urllib.error


def query_endpoint(url: str, api_key: str, query: str) -> Dict[str, Any]:
    """Send query to /predict endpoint and return response."""
    request_data = json.dumps({"query": query}).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=request_data,
        headers={
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode('utf-8')}
    except Exception as e:
        return {"error": str(e)}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load queries from JSONL file."""
    out = []
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


def run_eval(endpoint_url: str, api_key: str, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run evaluation against remote endpoint."""
    latencies = []
    refusals = 0
    clarifies = 0
    low_conf = 0
    hits = 0
    errors = 0
    results = []
    
    t0 = time.time()
    for item in queries:
        q = item.get("query")
        if not q:
            continue
        
        print(f"Testing: {item.get('id')} - {q}")
        
        q_start = time.time()
        response = query_endpoint(endpoint_url, api_key, q)
        latency_ms = int((time.time() - q_start) * 1000)
        latencies.append(latency_ms)
        
        if "error" in response:
            errors += 1
            results.append({
                "id": item.get("id"),
                "query": q,
                "error": response.get("error"),
                "latency_ms": latency_ms
            })
            continue
        
        pred = response.get("prediction", {})
        failure_mode = pred.get("failure_mode")
        confidence = pred.get("confidence", 0.0)
        citations = pred.get("citations", [])
        
        if failure_mode == "refuse":
            refusals += 1
        elif failure_mode == "clarify":
            clarifies += 1
        elif failure_mode == "low_confidence":
            low_conf += 1
        else:
            if citations:
                hits += 1
        
        results.append({
            "id": item.get("id"),
            "query": q,
            "answer": pred.get("answer"),
            "failure_mode": failure_mode,
            "confidence": confidence,
            "citations": citations,
            "latency_ms": latency_ms,
            "expected_behavior": item.get("expected_behavior"),
            "notes": item.get("notes")
        })
    
    elapsed_s = time.time() - t0
    count = len(results)
    
    p50 = statistics.median(latencies) if latencies else 0
    p95 = (int(statistics.quantiles(latencies, n=100)[94]) 
           if len(latencies) >= 20 
           else max(latencies) if latencies else 0)
    
    summary = {
        "count": count,
        "elapsed_s": round(elapsed_s, 2),
        "errors": errors,
        "hit_rate": round(hits / count, 3) if count else 0.0,
        "refusal_rate": round(refusals / count, 3) if count else 0.0,
        "clarify_rate": round(clarifies / count, 3) if count else 0.0,
        "low_confidence_rate": round(low_conf / count, 3) if count else 0.0,
        "latency_p50_ms": int(p50),
        "latency_p95_ms": p95,
    }
    
    return {"summary": summary, "results": results}


def main(argv: List[str]) -> int:
    if len(argv) < 4:
        print("Usage: python run_eval_remote.py <endpoint_url> <api_key> <queries.jsonl> [--out results.json]")
        print("Example: python run_eval_remote.py http://localhost:8000/predict dev-api-key eval/queries.jsonl --out eval/results.json")
        return 2
    
    endpoint_url = argv[1]
    api_key = argv[2]
    queries_file = argv[3]
    
    outfile = None
    if "--out" in argv:
        idx = argv.index("--out")
        if idx + 1 < len(argv):
            outfile = argv[idx + 1]
    
    queries = load_jsonl(queries_file)
    print(f"Loaded {len(queries)} queries from {queries_file}")
    print(f"Testing endpoint: {endpoint_url}")
    print("-" * 60)
    
    report = run_eval(endpoint_url, api_key, queries)
    
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    for key, value in report["summary"].items():
        print(f"{key:25s}: {value}")
    
    out_json = json.dumps(report, indent=2)
    if outfile:
        Path(outfile).write_text(out_json, encoding="utf-8")
        print(f"\n✓ Wrote full results to {outfile}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
