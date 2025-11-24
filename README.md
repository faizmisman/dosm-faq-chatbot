# DOSM FAQ Chatbot - Deployment & Testing Guide

> **Phase P5 Complete**: Production-ready RAG chatbot for DOSM economic data queries  
> **Performance**: 90% hit rate, 197ms p95 latency, 0% error rate  
> **Architecture**: Dual-cluster (dev/prod), MLflow tracking, pgvector storage

## 🎯 Quick Start for Testers

### Prerequisites
```bash
# Azure CLI authenticated
az login

# kubectl installed
kubectl version --client

# Python 3.10+ with dependencies
pip install requests pandas mlflow sentence-transformers
```

### Test Dev Environment
```bash
# 1. Connect to dev cluster
az aks get-credentials \
  --resource-group dosm-faq-chatbot-dev-rg \
  --name dosm-faq-chatbot-dev-aks

# 2. Check deployment status
kubectl get pods -n dosm-dev
# Expected: 2 API pods Running, 1 MLflow pod Running

# 3. Port-forward API
kubectl port-forward svc/faq-chatbot-dosm-insights 8000:80 -n dosm-dev &

# 4. Test query
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key" \
  -d '{"query":"What is the unemployment rate in 2023?"}'

# Expected response:
# {
#   "answer": "Based on the data...",
#   "confidence": 0.85,
#   "sources": [...],
#   "needs_clarification": false
# }
```

### Test Production Environment
```bash
# 1. Connect to prod cluster
az aks get-credentials \
  --resource-group dosm-faq-chatbot-prod-rg \
  --name dosm-faq-chatbot-prod-aks

# 2. Check deployment (with canary support)
kubectl get pods -n dosm-prod
kubectl get canary -n dosm-prod
kubectl get svc -n ingress-nginx  # External IP: 57.158.128.224

# 3. Test via public endpoint (no port-forward needed!)
curl -X POST http://dosm-faq-prod.57.158.128.224.nip.io/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: prod-placeholder" \
  -d '{"query":"employment statistics 2024"}'

# Health check
curl http://dosm-faq-prod.57.158.128.224.nip.io/health

# Alternative: Direct IP access
curl -X POST http://57.158.128.224/predict \
  -H "Content-Type: application/json" \
  -H "Host: dosm-faq-prod.57.158.128.224.nip.io" \
  -H "X-API-Key: prod-placeholder" \
  -d '{"query":"employment statistics 2024"}'

# Note: Using nip.io for DNS (maps *.57.158.128.224.nip.io → 57.158.128.224)
# For custom domain, update DNS A record and deploy/helm/values-prod.yaml
```

### Test ML Pipeline
```bash
# 1. Check MLflow UI
open http://20.6.121.120:5000

# 2. View rag-ingestion experiment
# Navigate to: Experiments → rag-ingestion
# Check latest run: 117 rows → 5 chunks → 5 embeddings

# 3. Verify database embeddings
PGPASSWORD='Kusanagi@2105' psql \
  -h pg-dosm.postgres.database.azure.com \
  -U dosm_admin \
  -d dosm-faq-chatbot-dev-postgres \
  -c "SELECT COUNT(*), MAX(created_at) FROM embeddings;"

# Expected: 5 embeddings with recent timestamp

# 4. Check next scheduled run
kubectl get cronjob -n dosm-dev rag-ingest
# Schedule: 0 18 * * * (02:00 MYT daily)
```

### Run Evaluation Suite
```bash
# 1. Port-forward dev API
kubectl port-forward svc/faq-chatbot-dosm-insights 8000:80 -n dosm-dev &

# 2. Run unemployment queries test
python3 scripts/run_eval_remote.py \
  http://localhost:8000/predict \
  dev-api-key \
  eval/queries_unemployment.jsonl \
  --out eval/results_test.json

# 3. Check results
python3 -c "
import json
with open('eval/results_test.json') as f:
    data = json.load(f)
    print(f'Hit Rate: {data[\"summary\"][\"hit_rate\"]*100:.0f}%')
    print(f'Avg Latency: {data[\"summary\"][\"avg_latency_ms\"]:.0f}ms')
    print(f'Errors: {data[\"summary\"][\"error_rate\"]*100:.0f}%')
"

# Expected: ≥85% hit rate, <500ms latency, 0% errors
```

---

## 🏗️ Architecture Overview

### System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                        User Query                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │   API Gateway/LB      │
         │   (AKS Ingress)       │
         └──────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────┐       ┌───────────────┐
│  Dev Cluster  │       │ Prod Cluster  │
│  (D2s_v3)     │       │  (E2s_v3)     │
│  8GB RAM      │       │  16GB RAM     │
└───────┬───────┘       └───────┬───────┘
        │                       │
        │    ┌──────────────────┘
        │    │
        ▼    ▼
┌─────────────────────────────────┐
│   FastAPI Application           │
│   ├─ Request Validation         │
│   ├─ Query Embedding            │
│   ├─ Vector Similarity Search   │
│   └─ LLM Answer Generation      │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│   PostgreSQL (pgvector)         │
│   ├─ embeddings table           │
│   │   └─ 384-dim vectors        │
│   ├─ HNSW index (fast search)   │
│   └─ GIN index (metadata)       │
└─────────────────────────────────┘
```

### ML Pipeline Architecture (Simplified)
```
┌─────────────────────────────────────────────────────────────┐
│              Daily 02:00 MYT - CronJob                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌────────────────────┐
         │  rag_ingest.py     │
         │  (Single Script)   │
         └─────────┬──────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
      ▼            ▼            ▼
┌─────────┐  ┌──────────┐  ┌────────────┐
│ Fetch   │→ │  Chunk   │→ │  Embed     │
│ DOSM    │  │  Data    │  │  Generate  │
│ CSV     │  │  (25rows)│  │  (MiniLM)  │
└─────────┘  └──────────┘  └─────┬──────┘
                                  │
                    ┌─────────────┴──────────────┐
                    │                            │
                    ▼                            ▼
            ┌───────────────┐          ┌─────────────────┐
            │   Validate    │          │   MLflow Track  │
            │   Embeddings  │          │   Experiment    │
            └───────┬───────┘          └─────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │   Store to    │
            │   PostgreSQL  │
            └───────────────┘
```

### Key Design Decisions

#### 1. **Simplified ML Pipeline (YAGNI Principle)**
- ❌ **Removed**: Apache Airflow (complex orchestration)
- ✅ **Using**: Simple Python script + Kubernetes CronJob
- **Why**: Daily batch job doesn't need DAG complexity
- **Benefits**: 
  - 90% less code (164 lines vs 1000+)
  - 50% less memory (512Mi vs 2Gi+)
  - 100% less storage (0 PVCs vs 100Gi+)
  - Zero Airflow maintenance

#### 2. **MLflow Standalone Tracking**
- ✅ **Keeps**: MLflow for experiment tracking
- **Purpose**: Track metrics, parameters, model versions
- **Integration**: Python script logs directly to MLflow
- **Access**: LoadBalancer at http://20.6.121.120:5000

#### 3. **Dual-Cluster Strategy**
- **Dev**: Rapid iteration, testing, evaluation
- **Prod**: Stable releases with canary deployments
- **Separation**: Prevents dev workload from affecting prod

#### 4. **Vector Database Choice**
- **PostgreSQL + pgvector** over Chroma/Pinecone
- **Why**: 
  - Lower latency (50ms vs 100ms+)
  - Centralized data management
  - ACID compliance
  - Cost-effective (no external service)

---

## 📊 Testing Scenarios

### 1. Functional Testing

#### Test Case: Basic Query
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key" \
  -d '{
    "query": "What is the unemployment rate in Selangor for 2023?"
  }'
```

**Expected**:
- ✅ HTTP 200 status
- ✅ `answer` field with relevant data
- ✅ `confidence` between 0.7-1.0
- ✅ `sources` array with references
- ✅ `needs_clarification: false`

#### Test Case: Ambiguous Query
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key" \
  -d '{
    "query": "unemployment"
  }'
```

**Expected**:
- ✅ HTTP 200 status
- ✅ `needs_clarification: true`
- ✅ Clarifying questions in response
- ✅ `confidence` < 0.25 (threshold)

#### Test Case: Invalid API Key
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: wrong-key" \
  -d '{"query":"test"}'
```

**Expected**:
- ✅ HTTP 401 Unauthorized
- ✅ Error message about API key

### 2. Performance Testing

#### Latency Test (Warm)
```bash
# Run 10 queries and measure p95 latency
for i in {1..10}; do
  time curl -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -H "X-API-Key: dev-api-key" \
    -d '{"query":"unemployment 2023"}' \
    -w "\nTime: %{time_total}s\n"
done
```

**Expected**: p95 < 500ms (target: ~200ms)

#### Cold Start Test
```bash
# Scale down, then scale up and test
kubectl scale deployment faq-chatbot-dosm-insights -n dosm-dev --replicas=0
sleep 10
kubectl scale deployment faq-chatbot-dosm-insights -n dosm-dev --replicas=2
sleep 30  # Wait for pods to start
# Run query and measure time
```

**Expected**: First query < 15s (model loading)

### 3. Load Testing

```bash
# Using Apache Bench
ab -n 100 -c 10 -T 'application/json' -H 'X-API-Key: dev-api-key' \
  -p <(echo '{"query":"unemployment 2023"}') \
  http://localhost:8000/predict
```

**Expected**:
- ✅ 100% success rate
- ✅ Mean time < 500ms
- ✅ No 5xx errors

### 4. ML Pipeline Testing

#### Manual Pipeline Run
```bash
# Trigger manual job
kubectl create job --from=cronjob/rag-ingest rag-ingest-manual -n dosm-dev

# Watch execution
kubectl logs -n dosm-dev -l job-name=rag-ingest-manual -f

# Verify completion
kubectl get job -n dosm-dev rag-ingest-manual
# STATUS: Complete (1/1)
```

**Expected Output**:
```
🚀 RAG Ingestion Pipeline Starting - 2025-11-25
📊 MLflow URI: http://mlflow.mlflow.svc.cluster.local:5000
🗄️  Database: pg-dosm.postgres.database.azure.com:5432
🚀 Starting RAG ingestion pipeline for 2025-11-25
📥 Step 1: Fetching DOSM data...
   ✓ Fetched 117 rows
✂️  Step 2: Chunking data (chunk_size=25)...
   ✓ Created 5 chunks
🧠 Step 3: Generating embeddings...
   ✓ Generated 5 embeddings
✅ Step 4: Validating embeddings...
   ✓ Validation passed
💾 Step 5: Storing to PostgreSQL...
   ✓ Stored 5 embeddings

✨ Pipeline completed successfully!
   MLflow tracking: http://mlflow.mlflow.svc.cluster.local:5000
```

#### Verify MLflow Tracking
```bash
# Check experiment
curl -s 'http://20.6.121.120:5000/api/2.0/mlflow/experiments/search?max_results=10' \
  | python3 -m json.tool \
  | grep -A 5 "rag-ingestion"

# Check latest run
curl -s 'http://20.6.121.120:5000/api/2.0/mlflow/runs/search' \
  -H 'Content-Type: application/json' \
  -d '{"experiment_ids": ["1"], "max_results": 1}' \
  | python3 -m json.tool
```

**Expected Metrics**:
- ✅ `row_count`: 117
- ✅ `chunk_count`: 5
- ✅ `embedding_count`: 5
- ✅ `stored_count`: 5
- ✅ `validation_passed`: 1.0

### 5. Database Testing

```bash
# Connect to database
PGPASSWORD='Kusanagi@2105' psql \
  -h pg-dosm.postgres.database.azure.com \
  -U dosm_admin \
  -d dosm-faq-chatbot-dev-postgres

# Run tests
-- Check embeddings count
SELECT COUNT(*) FROM embeddings;
-- Expected: ≥5

-- Check embedding dimensions
SELECT id, LENGTH(embedding::text) 
FROM embeddings LIMIT 1;
-- Expected: 384 dimensions

-- Check metadata
SELECT id, content, metadata->>'start_row', metadata->>'end_row' 
FROM embeddings LIMIT 3;
-- Expected: Proper row ranges

-- Test vector search
SELECT id, content, 
       1 - (embedding <=> '[0.1,0.2,...]'::vector) AS similarity
FROM embeddings
ORDER BY embedding <=> '[0.1,0.2,...]'::vector
LIMIT 3;
-- Expected: Results ordered by similarity
```

---

## 🚀 Deployment Process

### Dev Deployment
```bash
# 1. Build and push image
docker buildx build --platform linux/amd64 \
  -t dosmfaqchatbotacr1lw5a.azurecr.io/dosm-faq-chatbot:$(git rev-parse --short HEAD) \
  --push .

# 2. Deploy via Helm
helm upgrade --install faq-chatbot-dev deploy/helm \
  --namespace dosm-dev \
  --values deploy/helm/values-dev.yaml \
  --set image.tag=$(git rev-parse --short HEAD) \
  --wait --timeout=10m

# 3. Verify deployment
kubectl get pods -n dosm-dev
kubectl rollout status deployment/faq-chatbot-dosm-insights -n dosm-dev

# 4. Run smoke tests
kubectl port-forward svc/faq-chatbot-dosm-insights 8000:80 -n dosm-dev &
python3 scripts/smoke_test.py http://localhost:8000 dev-api-key
```

### Production Deployment (via GitHub Actions)
```bash
# Trigger via git push to main
git add .
git commit -m "Release: vX.Y.Z - Description"
git push origin main

# GitHub Actions workflow:
# 1. Build multi-arch image (AMD64)
# 2. Push to ACR
# 3. Deploy to prod cluster
# 4. Flagger starts canary analysis
#    - 0% → 10% → 20% → 30% → 50% traffic shift
#    - Metrics checks at each step
#    - Auto-rollback on failures
# 5. Full promotion after 30min success

# Monitor canary
kubectl get canary -n dosm-prod -w

# Manual rollback if needed
kubectl rollout undo deployment/faq-chatbot-dosm-insights-primary -n dosm-prod
```

---

## 📈 Monitoring & Observability

### Check Application Logs
```bash
# Dev logs
kubectl logs -n dosm-dev deployment/faq-chatbot-dosm-insights --tail=100 -f

# Prod logs
kubectl logs -n dosm-prod deployment/faq-chatbot-dosm-insights-primary --tail=100 -f

# Filter errors
kubectl logs -n dosm-dev deployment/faq-chatbot-dosm-insights | grep ERROR
```

### Check Resource Usage
```bash
# Pod resource consumption
kubectl top pods -n dosm-dev

# Node resource consumption
kubectl top nodes

# Describe pod for resource limits
kubectl describe pod -n dosm-dev -l app=dosm-insights
```

### MLflow Metrics
```bash
# Open MLflow UI
open http://20.6.121.120:5000

# Check via API
curl http://20.6.121.120:5000/api/2.0/mlflow/experiments/list | jq
```

### Database Health
```bash
# Connection test
PGPASSWORD='Kusanagi@2105' psql \
  -h pg-dosm.postgres.database.azure.com \
  -U dosm_admin \
  -d dosm-faq-chatbot-dev-postgres \
  -c "SELECT version();"

# Check embeddings freshness
PGPASSWORD='Kusanagi@2105' psql \
  -h pg-dosm.postgres.database.azure.com \
  -U dosm_admin \
  -d dosm-faq-chatbot-dev-postgres \
  -c "SELECT COUNT(*), MAX(created_at), MIN(created_at) FROM embeddings;"
```

---

## 🔧 Troubleshooting Guide

### Issue: API Returns 500 Error

**Symptoms**: `{"detail": "Internal server error"}`

**Diagnosis**:
```bash
# Check pod logs
kubectl logs -n dosm-dev deployment/faq-chatbot-dosm-insights --tail=50

# Check pod status
kubectl describe pod -n dosm-dev -l app=dosm-insights
```

**Common Causes**:
1. Database connection failure → Check `DATABASE_URL` secret
2. Model loading failure → Check memory limits (need ≥1Gi)
3. Missing environment variables → Check configmap/secrets

### Issue: Pipeline Job Fails

**Symptoms**: CronJob shows `Failed` status

**Diagnosis**:
```bash
# Check job logs
kubectl logs -n dosm-dev -l job-name=rag-ingest-<timestamp>

# Check job status
kubectl describe job -n dosm-dev rag-ingest-<timestamp>
```

**Common Causes**:
1. Database connection → Check URL encoding (@ = %40)
2. MLflow unreachable → Check MLflow pod status
3. Data source unavailable → DOSM CSV URL changed

**Fix**:
```bash
# Recreate secret with correct URL encoding
kubectl delete secret database-secrets -n dosm-dev
kubectl create secret generic database-secrets -n dosm-dev \
  --from-literal=DATABASE_URL='postgresql://dosm_admin:Kusanagi%402105@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-dev-postgres?sslmode=require'

# Restart MLflow if needed
kubectl rollout restart deployment/mlflow -n mlflow
```

### Issue: Low Hit Rate in Evaluation

**Symptoms**: Hit rate < 85%

**Diagnosis**:
```bash
# Check query results in detail
python3 scripts/run_eval_remote.py \
  http://localhost:8000/predict \
  dev-api-key \
  eval/queries_unemployment.jsonl \
  --out eval/debug_results.json

# Inspect failed queries
jq '.results[] | select(.hit == false)' eval/debug_results.json
```

**Common Causes**:
1. Stale embeddings → Run pipeline manually
2. Wrong confidence threshold → Check `CONF_THRESHOLD` env var
3. Insufficient RAG context → Check `RAG_TOP_K` setting

**Fix**:
```bash
# Trigger fresh embedding generation
kubectl create job --from=cronjob/rag-ingest rag-ingest-refresh -n dosm-dev

# Adjust RAG parameters (if needed)
kubectl set env deployment/faq-chatbot-dosm-insights \
  CONF_THRESHOLD=0.20 \
  RAG_TOP_K=5 \
  -n dosm-dev
```

### Issue: Pod Stuck in CrashLoopBackOff

**Symptoms**: Pod restarts repeatedly

**Diagnosis**:
```bash
# Check recent logs from crashed container
kubectl logs -n dosm-dev -l app=dosm-insights --previous

# Check events
kubectl get events -n dosm-dev --sort-by='.lastTimestamp'
```

**Common Causes**:
1. OOMKilled → Increase memory limit
2. Database unreachable → Check network/firewall
3. Missing secrets → Check secret existence

### Issue: Canary Stuck or Failed (Prod)

**Symptoms**: Canary not progressing

**Diagnosis**:
```bash
# Check canary status
kubectl describe canary faq-chatbot-dosm-insights -n dosm-prod

# Check Flagger logs
kubectl logs -n flagger-system deployment/flagger -f
```

**Manual Actions**:
```bash
# Skip analysis and promote
kubectl patch canary faq-chatbot-dosm-insights -n dosm-prod \
  --type=json -p='[{"op":"replace","path":"/spec/skipAnalysis","value":true}]'

# Rollback canary
kubectl rollout undo deployment/faq-chatbot-dosm-insights-primary -n dosm-prod
```

---

## 📚 Key Files & Directories

```
dosm-faq-chatbot/
├── README.md                     ← This file (deployment guide)
├── app/                          ← FastAPI application
│   ├── main.py                   ← API endpoints
│   ├── llm_rag/                  ← RAG pipeline modules
│   │   ├── rag_pipeline.py       ← Core RAG logic
│   │   ├── embeddings.py         ← Vector search
│   │   └── llm_provider.py       ← LLM integration
│   └── config.py                 ← Configuration
├── scripts/
│   ├── rag_ingest.py             ← ML pipeline (standalone)
│   ├── run_eval_remote.py        ← Evaluation script
│   └── smoke_test.py             ← Deployment verification
├── deploy/
│   ├── helm/                     ← Helm charts (dev/prod)
│   │   ├── values-dev.yaml
│   │   └── values-prod.yaml
│   ├── k8s/
│   │   └── rag-ingest-cronjob.yml ← Daily ingestion job
│   ├── mlflow-deployment.yaml    ← MLflow tracking server
│   └── rag-ingest.Dockerfile     ← Pipeline container image
├── eval/
│   ├── queries_unemployment.jsonl ← Test queries
│   └── results_phase5_final.json  ← Phase P5 results
├── sql/
│   └── migrations/               ← Database schemas
│       ├── 001_init_requests.sql
│       └── 002_vector_store.sql
└── development-docs/
    ├── QUICKREF.md               ← Quick command reference
    ├── DATABASE_CONFIG.md        ← Database setup guide
    ├── OPERATIONS.md             ← Production operations
    └── PHASE_P5_SUMMARY.md       ← Phase P5 report
```

---

## 🎓 Learning Resources

### Understanding RAG (Retrieval-Augmented Generation)
1. **Vector Embeddings**: Text converted to 384-dim vectors for similarity
2. **Semantic Search**: Find relevant chunks using cosine similarity
3. **Context Injection**: Top-K chunks fed to LLM for grounded answers
4. **Confidence Scoring**: Threshold-based clarification triggering

### Understanding Kubernetes Deployments
- **Pods**: Smallest deployable units (containers)
- **Deployments**: Manage pod replicas and updates
- **Services**: Expose pods via stable endpoint
- **ConfigMaps/Secrets**: External configuration
- **CronJobs**: Scheduled batch jobs

### Understanding Canary Deployments
1. **Traffic Shift**: Gradual routing (0% → 100%)
2. **Metrics Analysis**: Automated health checks
3. **Auto-Rollback**: Revert on failure
4. **Zero-Downtime**: Always maintains healthy pods

---

## 📞 Support & Contribution

### Getting Help
- Check `development-docs/` for detailed guides
- Review pod logs for error messages
- Verify secrets and configuration
- Test database connectivity

### Reporting Issues
Include:
1. Environment (dev/prod)
2. Kubernetes cluster name
3. Pod logs (`kubectl logs`)
4. Event logs (`kubectl get events`)
5. Steps to reproduce

### Development Workflow
1. Clone repo and create branch
2. Make changes locally
3. Test in dev cluster
4. Create PR with test results
5. GitHub Actions auto-deploys to prod on merge

---

## 📊 Performance Benchmarks (Phase P5)

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| Hit Rate | ≥85% | 90% | ✅ |
| p95 Latency (warm) | <500ms | 197ms | ✅ |
| p95 Latency (cold) | <15s | 11.8s | ✅ |
| Clarify Rate | 10-20% | 10% | ✅ |
| Error Rate | <5% | 0% | ✅ |

### Query Examples (from evaluation)
- ✅ "unemployment rate 2023" → HIT (conf: 0.85)
- ✅ "Selangor employment statistics" → HIT (conf: 0.78)
- ✅ "youth unemployment trend" → HIT (conf: 0.82)
- ⚠️ "unemployment" → CLARIFY (conf: 0.15)

---

## 🔐 Security Notes

### API Authentication
- Required: `X-API-Key` header
- Dev key: `dev-api-key`
- Prod key: Managed via Azure Key Vault (not in repo)

### Database Access
- SSL required (`sslmode=require`)
- Credentials stored in Kubernetes secrets
- Password URL-encoded in connection strings

### Network Policies
- Dev: Open for testing
- Prod: Ingress-only access
- MLflow: Cluster-internal only (no external exposure in prod)

---

**Documentation Version**: 1.0 (Post-Airflow Simplification)  
**Last Updated**: November 25, 2025  
**Status**: Production Ready ✅
