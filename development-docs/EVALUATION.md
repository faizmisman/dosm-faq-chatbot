# Evaluation Guide

Goal: verify **grounding**, **helpfulness**, **honesty**, and **latency** before promotion.

## 1) Eval dataset

Format: JSONL (`eval/queries.jsonl`)

```json
{"id":"cpi_2023","query":"What is Malaysia's CPI in 2023?","expected_behavior":"answer","notes":"national CPI row","expected_citation_hint":"year=2023"}
```

Coverage ≥15:
- simple lookups, comparisons, ambiguous, out‑of‑scope, missing data.

## 2) Running evaluation

Example CLI (you provide wrapper around `evaluators.py`):

```bash
python -m app.llm_rag.evaluators --eval-file eval/queries.jsonl --out eval/results.jsonl
```

The script records:
- retrieved chunks (ids/scores), citations,
- final decision (answer/clarify/refuse),
- latency per query.

## 3) Metrics

- **Retrieval hit‑rate**: % of answered queries where truth evidence is in top‑k.  
- **Hallucination rate**: % of answered queries judged incorrect/unsupported (label subset in `eval/labels.jsonl`).  
- **Latency**: p50/p95 ms.  
- **Behaviour accuracy**: correct clarify/refuse actions for relevant cases.

## 4) Reporting template

| Date | Commit | Model | Dataset Ver | Hit‑rate | Hallucination | p95 (ms) | Notes |
|---|---|---|---|---|---|---|---|
| 2025-11-21 | abc1234 | dosm‑rag‑v1.0 | 2025‑01 | 0.86 | 0.10 | 950 | baseline |

## 5) When to re‑run

- Any change to chunking/embeddings/prompt/LLM.  
- Dataset refresh.  
- Before prod promotion.  
