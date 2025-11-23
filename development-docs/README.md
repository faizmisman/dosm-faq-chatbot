# DOSM Insights Platform

A production-grade **RAG FAQ service** over Malaysia’s DOSM open data, deployed on **Azure Kubernetes Service (AKS)** with full **MLOps, observability, and CI/CD**.

This single project is designed to satisfy **both**:

- **LLM Engineer take-home** – RAG chatbot over a DOSM dataset using a workflow builder (e.g. Dify/n8n), with citations, evaluation, and responsible AI behaviour.
- **MLOps Engineer take-home** – A robust inference service with `/predict`, K8s deployment, CI/CD via GitHub Actions, monitoring (Prometheus/Grafana), PostgreSQL logging, and rollback strategies.

---

## 1. High-Level Overview

### 1.1 What this project does

- Ingests a **single dataset** from the DOSM Open Data Portal (e.g. CPI / unemployment / median income).
- Builds a **RAG pipeline** (chunking + embeddings + vector store) for grounded Q&A.
- Exposes a **FastAPI** service with:
  - `POST /predict` – answer questions with citations, latency, and model version.
  - `GET /healthz` – health check for K8s.
  - `GET /metrics` – Prometheus metrics endpoint.
- Integrates with a **workflow builder** (Dify or n8n) to provide a conversational **chat UI**.
- Logs all requests and responses to **PostgreSQL** and exposes dashboards via **Grafana**.
- Uses **GitHub Actions** for CI/CD and deployment to **Azure**.

### 1.2 Key Features

- **RAG + Citations**
  - Chunked ingestion of DOSM dataset.
  - Embedding-based retrieval using FAISS/Chroma.
  - Answers always include citations (source URL + snippet + row/page).

- **Responsible AI**
  - Explicit handling of:
    - Out-of-scope questions.
    - Outdated or missing data.
    - Low-confidence retrieval/answers (clarifying question or refusal).

- **Production MLOps**
  - AKS deployment with 2+ replicas and Ingress.
  - Observability via Prometheus & Grafana (RPS, p95 latency, error rate, CPU/memory).
  - PostgreSQL request logging & simple model registry.
  - CI/CD with GitHub Actions, including canary rollout and rollback docs.

---

## 2. Repository Structure

```text
.
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app: /predict, /healthz, /metrics
│   ├── config.py
│   ├── schemas.py               # Pydantic request/response models
│   ├── logging_utils.py         # Structured logging
│   └── llm_rag/
│       ├── rag_pipeline.py      # Core RAG query → answer + citations
│       ├── chunking.py          # Chunking strategy for DOSM data
│       ├── embeddings.py        # Embedding + vector store abstraction
│       └── evaluators.py        # Offline evaluation utilities
│
├── train/
│   ├── train_rag_assets.py      # Build vector store, log to MLflow, register version
│   └── dataset_card.md          # Data card for chosen DOSM dataset
│
├── pipelines/
│   ├── airflow_dag.py           # Or Prefect/Kubeflow pipeline for data → train → register
│   └── mlflow_register.py
│
├── workflows/
│   ├── dify_flow.json           # Or n8n export of the chat workflow
│   └── workflow_readme.md       # How the workflow is wired to /predict
│
├── deploy/
│   ├── k8s/
│   │   ├── deployment.yml       # AKS Deployment (2+ replicas)
│   │   ├── service.yml          # ClusterIP service
│   │   ├── ingress.yml          # NGINX/Kong Ingress + rate limiting/API key
│   │   └── hpa.yml              # Horizontal Pod Autoscaler
│   └── helm/
│       ├── Chart.yaml
│       └── values-*.yaml        # dev/prod values
│
├── dashboards/
│   └── grafana/
│       ├── dosm_insights_dashboard.json
│       └── README.md
│
├── sql/
│   └── migrations/
│       └── 001_init_requests.sql   # PostgreSQL DDL for inference_requests table
│
├── tests/
│   ├── test_rag_pipeline.py
│   ├── test_api_predict.py
│   └── test_chunking.py
│
├── .github/
│   └── workflows/
│       ├── ci.yml                # lint + tests + Docker build & push to ACR
│       ├── deploy-dev.yml        # deploy to dev AKS on main merge
│       └── promote-prod.yml      # manual canary → full prod rollout
│
├── MODEL_CARD.md
├── README.md
├── ARCHITECTURE.md
└── docs/
    ├── EVALUATION.md
    └── OPERATIONS.md

------------------

## Quickstart

1) **Pick a dataset** and fill `train/dataset_card.md` (template snippet is in ARCHITECTURE.md).  
2) Implement the minimal API surface described in `ARCHITECTURE.md` (copy/paste friendly contracts).  
3) Use `docs/DEVELOPMENT_GUIDE.md` to set up local env & tests.  
4) Deploy using `docs/OPERATIONS.md` procedures (AKS + Helm).  
5) Evaluate via `docs/EVALUATION.md` and export your Dify/n8n flow.  

---

## Azure resources (at a glance)

- **AKS**: 2–3× `Standard_D2s_v5` nodes (dev), HPA enabled.
- **ACR**: stores `dosm-insights-api` images.
- **PostgreSQL Flexible Server**: `B1ms` or `B2s` size for dev.
- **Storage Account**: raw DOSM files + vector artifacts (optional but recommended).
- **Key Vault**: secrets (`LLM_API_KEY`, `DATABASE_URL`, …) via Managed Identity.
- **Managed Prometheus + Managed Grafana** *or* self‑hosted in cluster.
- **Log Analytics**: container logs, Kusto queries.

See **ARCHITECTURE.md** for detailed SKUs, namespaces, and network notes.

---

## Status

- Docs version: 2025-11-21
- Next: implement `app/main.py` and `app/llm_rag/*` per the exact contracts inside `ARCHITECTURE.md`.
