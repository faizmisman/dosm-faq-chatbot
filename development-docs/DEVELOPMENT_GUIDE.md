# Development Guide

_Principles: KISS, YAGNI, fail fast, security‑first, consistency._

## 1) Prereqs

- Python 3.10+
- Docker (optional: local Postgres/Prom/Grafana)
- `kubectl`, `helm`, `az` (for deploys)
- Node.js only if you hack on Dify/n8n locally

## 2) Setup

```bash
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# (Optional) export ACR_NAME for build/push convenience
export ACR_NAME=dosmfaqchatbotacr1lw5a
```

Create `.env` (for **local only**):

```env
LLM_API_KEY=replace-me
EMBEDDING_API_KEY=replace-me
DATABASE_URL=postgresql://postgres:devpass@localhost:5432/dosm_insights
MODEL_VERSION=dosm-rag-local
LOG_LEVEL=INFO
```

> Shared envs: store secrets in **Key Vault** and inject via env from MSI.

## 3) Local services (optional)

**Postgres**:

```bash
docker run --name dosm-pg -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=dosm_insights -p 5432:5432 -d postgres:15
psql postgresql://postgres:devpass@localhost:5432/dosm_insights -f sql/migrations/001_init_requests.sql
```

## 4) RAG workflow

1. Fill `train/dataset_card.md` (see ARCHITECTURE.md snippet).  
2. Build artifacts:
   ```bash
   python train/train_rag_assets.py
   ```
3. Run API:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Try:
   ```bash
   curl -s localhost:8000/predict -H "Content-Type: application/json" -d '{"query":"CPI 2023?"}' | jq .
   ```

## 5) Tests & quality

```bash
pytest -q
ruff check .
# (optional) black . ; mypy app/ train/

## 5.1) Local Docker build

Requires Docker running. Builds both image names used across CI and Helm overrides:

```bash
docker build -t $ACR_NAME.azurecr.io/dosm-faq-chatbot:dev -t $ACR_NAME.azurecr.io/dosm-insights-api:dev .
az acr login -n $ACR_NAME
docker push $ACR_NAME.azurecr.io/dosm-faq-chatbot:dev
docker push $ACR_NAME.azurecr.io/dosm-insights-api:dev
```

Redeploy dev release referencing new tag:
```bash
helm upgrade --install faq-chatbot ./deploy/helm \
   -n dosm-dev -f deploy/helm/values-dev.yaml \
   --set secrets.enabled=false \
   --set env.API_KEY_SECRET=app-secrets --set env.API_KEY_KEY=API_KEY \
   --set env.DB.URL_SECRET=app-secrets --set env.DB.URL_KEY=DATABASE_URL \
   --set image.repository="$ACR_NAME.azurecr.io/dosm-faq-chatbot" \
   --set image.tag=dev
```

Run smoke test:
```bash
make smoke-dev
```

If pods stuck in `ImagePullBackOff` ensure image exists:
```bash
az acr repository list -n $ACR_NAME -o table
az acr repository show-tags -n $ACR_NAME --repository dosm-faq-chatbot -o table
```
```

Target **≥80%** coverage for core RAG + API.

## 6) Branching & PRs

- `main` is deployable.  
- Feature branches: `feature/<name>`; small, focused PRs.  
- Update docs on behaviour changes (README/ARCH/EVAL/OPS).

## 7) Contracts you must not break

- `/predict` response fields (see ARCHITECTURE.md).  
- Metrics endpoint name `/metrics`.  
- Refusal/clarification behaviour when confidence is low.

## 8) Useful env vars (suggested)

- `LLM_API_KEY`, `EMBEDDING_API_KEY`, `MODEL_VERSION`  
- `DATABASE_URL`, `AZURE_STORAGE_CONNECTION_STRING`  
- `LOG_LEVEL`, `PROMETHEUS_MULTIPROC_DIR` (if using multiproc)  

See `LOCAL_TESTING.md` for deeper guide on image build paths (local vs CI) and troubleshooting.
