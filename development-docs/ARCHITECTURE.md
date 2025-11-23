# Architecture – DOSM Insights Platform

This document is the **single source of truth** for how the system works and how it hits **both** take‑home requirements.

_Last updated: 2025-11-21_

---

## 1) System overview

**Concept:** A RAG chatbot answers questions **only** from a chosen DOSM dataset (e.g., CPI).  
**Interface:** A single FastAPI service with `/predict` (inference), `/metrics` (Prometheus), `/healthz` (readiness/liveness).  
**UX:** A no/low‑code workflow (Dify or n8n) calls `/predict` and renders a chat with citations; includes one extra action (e.g., export CSV).  
**Ops:** Runs on AKS with Helm, GitHub Actions CI/CD, PostgreSQL logging, Prometheus/Grafana, Key Vault secrets.

---

## 2) Detailed component design

### 2.1 Data layer

- **DOSM dataset**: CSV/Excel from DOSM Open Data Portal.  
- **Data card** (commit this as `train/dataset_card.md` when you add code):

```markdown
# Dataset Card – DOSM CPI (example)
- Source URL: https://…
- License: Open Government Data
- Last updated (portal): YYYY‑MM‑DD
- Refresh cadence: Monthly
- Fields: year, month, region, cpi_index, etc.
- Known gaps/quirks: ...
```

- **Storage (optional)**: Azure Storage containers
  - `dosm-raw` for raw downloads, `dosm-artifacts` for vector store snapshots.

### 2.2 RAG layer (to implement under `app/llm_rag/`)

- `chunking.py`: preserves headers & metadata (year/state/measure), configurable `chunk_size` & overlap.
- `embeddings.py`: provider abstraction (OpenAI/Cohere/local) + FAISS/Chroma helpers.
- `rag_pipeline.py`: the orchestrator
  1. retrieve top‑k
  2. build prompt with context + rules (answer only from context, cite sources, refuse/clarify)
  3. call LLM
  4. compute `confidence` & decide: **answer** | **clarify** | **refuse**
- `evaluators.py`: offline metrics (retrieval hit‑rate, hallucination rate, latency p50/p95).

### 2.3 API surface (FastAPI, `app/main.py`)

**Request** (`POST /predict`):

```json
{
  "query": "What is the CPI for Malaysia in 2023?",
  "user_id": "faiz",
  "tool_name": "dosm_faq"
}
```

**Response** (fields **must** exist):

```json
{
  "prediction": {
    "answer": "…",
    "citations": [{"source":"<url>","snippet":"…","page_or_row":12}],
    "confidence": 0.82,
    "failure_mode": null
  },
  "latency_ms": 523,
  "model_version": "dosm-rag-v1.3"
}
```

**Health & Metrics**:
- `GET /health` – lightweight checks (vector store readable, DB reachable).  
- `GET /metrics` – Prometheus registry (HTTP counters/histograms + RAG counters).

### 2.4 Workflow builder

- Dify/n8n flow:
  - `User → HTTP(POST /predict) → Mapper → Chat UI`
  - Extra action (example): **Export CPI slice to CSV** → signed URL from Azure Blob.
- Commit export as `workflows/<tool>_flow.json` and a short `workflow_readme.md`.

### 2.5 Observability

- Prometheus: scrape `/metrics` from API pods.
- Grafana: dashboard panels → RPS, p50/p95, error %, CPU/mem, refusal rate.
- Log Analytics: structured JSON logs (see DEVELOPMENT_GUIDE).

### 2.6 Data & request logging

- PostgreSQL table (DDL example):

```sql
create table if not exists inference_requests (
  id serial primary key,
  request_id uuid not null,
  created_at timestamptz default now(),
  user_id text,
  query text,
  answer text,
  model_version text,
  latency_ms integer,
  is_refusal boolean,
  is_low_confidence boolean
);
```

---

## 3) Azure topology (recommended)

| Layer | Resource | Notes / Starter SKU |
|---|---|---|
| Compute | **AKS** | 2–3× `Standard_D2s_v5` (dev). Namespaces: `dosm-dev`, `dosm-prod`. |
| Images | **ACR** | Private images for API and (optionally) Prom+Grafana if self‑hosted. |
| DB | **Azure Database for PostgreSQL – Flexible Server** | Burstable `B1ms`/`B2s` (dev), HA off; prod enable zone‑redundancy later. |
| Storage | **Storage Account** | Containers: `dosm-raw`, `dosm-artifacts`. |
| Secrets | **Key Vault** + **Managed Identity** | API reads secrets via MSI (no plain secrets in YAML). |
| Metrics | **Managed Prometheus + Grafana** or in‑cluster | If in‑cluster, install via Helm charts. |
| Logs | **Log Analytics** | Container logs + Kusto queries. |
| Edge | (Optional) **Azure Front Door + WAF** | If public internet exposure & stricter security needed. |

> Networking: start with Public LB + NGINX Ingress. For enterprise, consider AGIC or Private AKS + Front Door.

---

## 4) CI/CD (GitHub Actions blueprint)

- **ci.yml**: tests → build → push to ACR (OIDC), artifacts.
- **deploy-dev.yml**: on merge to `main` → `helm upgrade --install` to `dosm-dev` → smoke tests.
- **promote-prod.yml**: manual → canary (10%) → observe → promote 100% or rollback.

Helm values to vary:
- `image.repository`, `image.tag`
- env (Key Vault refs), replicas, resources, HPA thresholds
- Ingress hostnames & rate limits

Rollback:
- `helm rollback dosm-insights <rev>` or `kubectl rollout undo deployment/dosm-insights-api`

---

## 5) Non‑functional requirements (SLOs & security)

- **Availability**: 99%+ (demo), raise for real prod.  
- **Latency**: p95 < 1.5s (LLM‑dependent).  
- **Security**: HTTPS ingress, API key/JWT, per‑key rate‑limit, secrets in Key Vault, MSI for identity.  
- **Cost**: keep node pool small; monitor LLM token burn; start burstable Postgres tier.

---

## 6) Mapping to take‑home requirements

**LLM Engineer** → RAG + citations + workflow + evaluation + refusal logic.  
**MLOps Engineer** → `/predict` + AKS + CI/CD + metrics + DB logging + rollback + scaling.

See `docs/EVALUATION.md` and `docs/OPERATIONS.md` for exact procedures.

---

## 7) Next steps checklist

- [ ] Commit dataset card.
- [ ] Implement `app/` and `train/` per contracts above.
- [ ] Add Helm chart + minimal K8s manifests.
- [ ] Wire GitHub Actions with ACR/AKS OIDC.
- [ ] Export Dify/n8n flow.
- [ ] Run baseline evaluation and paste metrics in `docs/EVALUATION.md`.
