# Deployment Notes

## Dev Rollout Stability

To avoid Helm upgrade timeouts in dev due to CPU pressure and HPA enforcing extra replicas, keep dev simple:

- Use `Recreate` strategy and `replicaCount: 1` (already in `deploy/helm/values-dev.yaml`).
- Before upgrading, delete HPA and scale to one replica; use longer Helm timeout.

Commands:

```sh
kubectl delete hpa faq-chatbot-dosm-insights -n dosm-dev || true
kubectl scale deployment faq-chatbot-dosm-insights -n dosm-dev --replicas=1
helm upgrade --install faq-chatbot-dosm-insights deploy/helm -n dosm-dev -f deploy/helm/values-dev.yaml --timeout 10m --atomic=false
kubectl rollout status deployment faq-chatbot-dosm-insights -n dosm-dev --timeout=10m
```

Optional: re-create HPA conservatively after rollout:

```sh
kubectl autoscale deployment faq-chatbot-dosm-insights -n dosm-dev --min=1 --max=2 --cpu-percent=75
```

Note: Dev does not require canary. Prod canary via Flagger is unaffected.

## RAG Embedding Format Improvement

**Status**: ✅ **COMPLETED** (2025-11-29) - Both dev and prod databases now use improved embedding format.

**Change**: `app/llm_rag/chunking.py` now uses semicolon-separated fields:
```python
"; ".join([f"{col}={row[col]}" for col in df.columns])
```

**Current embeddings** (as of 2025-11-29 00:28 MYT):
- **Dev**: 5 embeddings with semicolon format (cleaned and re-ingested using `scripts/reingest_clean.py`)
- **Prod**: 5 embeddings with semicolon format (migrated from dev using `scripts/migrate_embeddings_dev_to_prod.py`)
- Verified format: `date=2016-01-01; unemployed=501.5; unemployed_active=361.9; ...`

**Important**: Prod ingestion strategy is to **copy validated embeddings from dev**, not regenerate independently. This ensures consistency and avoids model non-determinism.

**Improved format example:**
```
date=2016-01-01; unemployed=501.5; unemployed_active=361.9; unemployed_active_3mo=180.3; unemployed_active_6mo=110.0; unemployed_active_12mo=36.0; unemployed_active_long=35.6; unemployed_inactive=139.7
date=2016-02-01; unemployed=506.4; unemployed_active=254.0; unemployed_active_3mo=115.8; unemployed_active_6mo=83.7; unemployed_active_12mo=34.9; unemployed_active_long=19.6; unemployed_inactive=252.4
```

**Benefit**: Better semantic understanding for LLM retrieval; clearer field boundaries prevent token confusion like `unemployed_inactive=191.9date=2020-02-01`.

**Verification**: Use `od -c` to view actual byte content including separators and newlines:
```bash
# Dev database
kubectl config use-context dosm-faq-chatbot-dev-aks
kubectl get secret database-secrets -n dosm-dev -o jsonpath='{.data.DATABASE_URL}' | base64 -d > /tmp/dev_db_url.txt
psql "$(cat /tmp/dev_db_url.txt)" -c "SELECT content FROM embeddings WHERE id='chunk_0_25' LIMIT 1;" -A -t | od -c | head -40

# Prod database
kubectl config use-context dosm-faq-chatbot-prod-aks
kubectl get secret prod-db-url -n dosm-prod -o jsonpath='{.data.DATABASE_URL}' | base64 -d > /tmp/prod_db_url.txt
psql "$(cat /tmp/prod_db_url.txt)" -c "SELECT content FROM embeddings WHERE id='chunk_0_25' LIMIT 1;" -A -t | od -c | head -40
```

**Note**: Some SQL clients may display multi-line content as a single line, collapsing newlines. This is a display issue only - the actual database content is correct with semicolons and newlines.

## Production API Key Management

### GitHub Secrets
- **Secret Name**: `PROD_API_KEY`
- **Value**: `DosmProdApi2025!`
- **Location**: GitHub Repository → Settings → Secrets and variables → Actions

### Kubernetes Secrets Created by Pipeline
1. **prod-api-key**: Created from `PROD_API_KEY` GitHub Secret
2. **faq-chatbot-dosm-insights-config-primary**: Patched by pipeline for Flagger-managed pods

### How It Works
1. CI/CD pipeline (`deploy-prod.yml`) runs on workflow_dispatch or tag push
2. Pipeline creates `prod-api-key` secret from GitHub Secrets
3. Pipeline patches `faq-chatbot-dosm-insights-config-primary` (Flagger-managed secret)
4. Helm deployment uses `env.API_KEY_SECRET` and `env.API_KEY_KEY` from values-prod.yaml
5. Flagger creates `-primary` deployment for stable production traffic
6. Pods mount API key from secrets automatically

### Flagger Canary Deployment
- **Base Deployment**: `faq-chatbot-dosm-insights` (canary)
- **Stable Deployment**: `faq-chatbot-dosm-insights-primary` (production traffic)
- **Secret Used**: `faq-chatbot-dosm-insights-config-primary`

### Important
- **DO NOT** manually edit secrets after pipeline runs
- **DO NOT** modify Helm values for API key directly
- **ALWAYS** update `PROD_API_KEY` in GitHub Secrets
- **ALWAYS** trigger pipeline to deploy changes

### Testing
```bash
# Verify secret exists
kubectl get secret prod-api-key -n dosm-prod -o jsonpath='{.data.PROD_API_KEY}' | base64 -d

# Verify Flagger-managed secret
kubectl get secret faq-chatbot-dosm-insights-config-primary -n dosm-prod -o jsonpath='{.data.API_KEY}' | base64 -d

# Test endpoint
curl -X POST http://dosm-faq-prod.57.158.128.224.nip.io/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: DosmProdApi2025!" \
  -d '{"query":"What is the unemployment rate?"}'
```

### Deployment Flow
```
GitHub Secrets (PROD_API_KEY)
    ↓
CI/CD Pipeline (deploy-prod.yml)
    ↓
├─ Create: prod-api-key secret
└─ Patch: faq-chatbot-dosm-insights-config-primary
    ↓
Helm Deployment (values-prod.yaml)
    ↓
Flagger Canary Controller
    ↓
├─ faq-chatbot-dosm-insights (canary)
└─ faq-chatbot-dosm-insights-primary (production)
```
