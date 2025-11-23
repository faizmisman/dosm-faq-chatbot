# PostgreSQL pgvector Migration Guide

## Overview

This document describes the migration from file-based Chroma vector storage to PostgreSQL pgvector for improved scalability and deployment flexibility.

## Motivation

**Problem**: Previously, vector embeddings were stored as file artifacts (Chroma SQLite database) and baked into Docker images during build. This approach:
- Couples data with deployment artifacts
- Requires image rebuilds for dataset updates
- Doesn't scale with increasing data volumes
- Creates large Docker images

**Solution**: Use PostgreSQL pgvector extension to store embeddings in the database, enabling:
- Dynamic dataset ingestion without image rebuilds
- Horizontal scaling independent of data volume
- Unified data and vector storage
- Standard database backup/recovery procedures

## Architecture Changes

### Before (Chroma)
```
Docker Image:
  - Application code
  - Vector store files (artifacts/vector_store/)
  
Runtime:
  - Load Chroma from disk
  - Query via Chroma API
```

### After (pgvector)
```
Docker Image:
  - Application code only
  
Runtime:
  - Connect to PostgreSQL via DATABASE_URL
  - Query embeddings table via SQL
  - Use vector distance operators (<=>)
```

## Migration Steps

### 1. Database Setup

Run the migration SQL to create pgvector schema:

```bash
psql $DATABASE_URL -f sql/migrations/002_vector_store.sql
```

This creates:
- `vector` extension
- `embeddings` table with VECTOR(384) column
- HNSW index for fast cosine similarity search
- Helper functions: `search_embeddings()`, `upsert_embedding()`

### 2. Code Changes

**app/llm_rag/embeddings.py**:
- Refactored `VectorStoreWrapper` to use psycopg2 instead of Chroma
- `build_vector_store()` now inserts embeddings via batch SQL
- `load_vector_store()` connects to PostgreSQL instead of loading from disk
- Search uses native pgvector distance operator: `embedding <=> query_embedding`

**app/llm_rag/rag_pipeline.py**:
- Removed `VECTORSTORE_DIR` environment variable usage
- `_init_store_if_needed()` tries PostgreSQL first, falls back to dataset rebuild

**train/train_rag_assets.py**:
- Removed `--out-dir` argument (no longer writes files)
- Added optional `--metadata-dir` for JSON output
- Requires `DATABASE_URL` environment variable
- Inserts embeddings directly into PostgreSQL

### 3. Infrastructure Updates

**Dockerfile**:
- Removed `COPY artifacts/vector_store`
- Removed `ENV VECTORSTORE_DIR`
- Vector storage now accessed via `DATABASE_URL` at runtime

**Helm Templates**:
- `rag-ingest-job.yaml`: Added `DATABASE_URL` secret reference, removed `VECTORSTORE_DIR`
- `rag-ingest-cronjob.yaml`: Same changes as Job
- `deployment.yaml`: Removed `VECTORSTORE_DIR` environment variable
- `values-dev.yaml`: Removed `VECTORSTORE_DIR` and `outputDir` references

**.gitignore**:
- Added `artifacts/` to ignore vector store files
- Removed committed artifacts from git history

### 4. Dependencies

Added to `requirements.txt`:
```
pgvector>=0.2.0,<1.0.0
langchain-postgres>=0.0.9
```

Existing dependency:
```
psycopg2-binary>=2.9.0
```

## Deployment

### Resource Requirements

**Important**: The embedding model (sentence-transformers/all-MiniLM-L6-v2) downloads on first pod start and requires:
- **Memory**: 512Mi minimum (1Gi recommended)
- **CPU**: 250m minimum (1000m limit recommended)
- **Initial startup time**: ~26-30 seconds for model download

**Kubernetes Probe Configuration**:
```yaml
readinessProbe:
  initialDelaySeconds: 10
  timeoutSeconds: 5
  periodSeconds: 10
  failureThreshold: 3

livenessProbe:
  initialDelaySeconds: 60  # Allow time for model download
  timeoutSeconds: 10
  periodSeconds: 30
  failureThreshold: 3
```

**Helm Deployment Timeout**:
- Use `--wait --timeout 10m` (not 5m) to accommodate initial model download
- Subsequent deployments are faster as nodes cache the Docker image

### Local Testing

1. Set DATABASE_URL to local PostgreSQL instance:
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/dosm_dev"
```

2. Run migration:
```bash
psql $DATABASE_URL -f sql/migrations/002_vector_store.sql
```

3. Ingest data:
```bash
python -m train.train_rag_assets --input data/dosm_sample.csv
```

4. Start application:
```bash
uvicorn app.main:app --reload
```

### Kubernetes Deployment

**Prerequisites**:
1. PostgreSQL Flexible Server with pgvector extension enabled:
```bash
# Enable pgvector extension via Azure CLI
az postgres flexible-server parameter set \
  --resource-group dosm-faq-chatbot-data \
  --server-name pg-dosm \
  --name azure.extensions \
  --value "pgvector,pg_stat_statements"
```

2. Run migration on dev/prod databases:
```bash
# Dev
PGPASSWORD='YourPassword' psql \
  -h pg-dosm.postgres.database.azure.com \
  -U dosm_admin \
  -d dosm-faq-chatbot-dev-postgres \
  -f sql/migrations/002_vector_store.sql

# Prod
PGPASSWORD='YourPassword' psql \
  -h pg-dosm.postgres.database.azure.com \
  -U dosm_admin \
  -d dosm-faq-chatbot-prod-postgres \
  -f sql/migrations/002_vector_store.sql
```

3. Create Kubernetes secrets with URL-encoded passwords:
```bash
# IMPORTANT: Special characters in password must be URL-encoded
# @ -> %40, : -> %3A, / -> %2F, etc.

kubectl create secret generic dev-db-url -n dosm-dev \
  --from-literal=DATABASE_URL="postgresql://dosm_admin:Password%40123@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-dev-postgres?sslmode=require"

kubectl create secret generic prod-db-url -n dosm-prod \
  --from-literal=DATABASE_URL="postgresql://dosm_admin:Password%40123@pg-dosm.postgres.database.azure.com:5432/dosm-faq-chatbot-prod-postgres?sslmode=require"
```

4. Configure Helm values to reference external secrets:
```yaml
# values-dev.yaml
env:
  DB:
    URL_SECRET: dev-db-url
    URL_KEY: DATABASE_URL

resources:
  requests:
    cpu: 250m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi
```

5. Deploy via GitHub Actions workflow or manual helm upgrade:
```bash
helm upgrade --install faq-chatbot-dev ./deploy/helm \
  -f deploy/helm/values-dev.yaml \
  --set image.tag=$IMAGE_TAG \
  --wait --timeout 10m  # 10 minutes to allow model download
```

### Troubleshooting Deployments

**Helm Upgrade Timeout (context deadline exceeded)**:
- **Cause**: Helm `--wait` flag waits for all pods to be Ready. First pod start downloads embedding model (~100MB) which takes 26-30 seconds, potentially exceeding default readiness probe + timeout.
- **Solution**: Increase Helm timeout from 5m to 10m: `--wait --timeout 10m`
- **Note**: Helm may show "failed" status but pods deploy successfully. Verify with: `kubectl get pods -n dosm-dev`

**Pod Fails Readiness/Liveness Probes**:
- **Cause**: Model download during first request exceeds probe timeouts
- **Solution**: Increased `livenessProbe.initialDelaySeconds: 60` and `timeoutSeconds: 10`

**PostgreSQL Connection Error "could not translate host name"**:
- **Cause**: Special characters in DATABASE_URL password not URL-encoded
- **Solution**: Encode password: `@` → `%40`, `:` → `%3A`, `/` → `%2F`

**Insufficient CPU for Replica Scale-up**:
- **Cause**: AKS node pool at capacity, increased resource requests (250m CPU) prevent scheduling
- **Solution**: Temporarily reduce replicas or enable cluster autoscaler:
```bash
az aks nodepool update \
  --resource-group dosm-faq-chatbot-dev-rg \
  --cluster-name dosm-faq-chatbot-dev-aks \
  --name system \
  --enable-cluster-autoscaler \
  --min-count 1 \
  --max-count 3
```

## Vector Search Details

### SQL Query Pattern

```sql
SELECT id, content, metadata, 
       1 - (embedding <=> %s::vector) as similarity
FROM embeddings
ORDER BY embedding <=> %s::vector
LIMIT %s
```

**Key Points**:
- `<=>` is pgvector's cosine distance operator
- `1 - distance` converts distance to similarity score
- HNSW index enables fast approximate nearest neighbor search
- Returns results ordered by similarity (highest first)

### Index Configuration

```sql
CREATE INDEX embeddings_embedding_idx 
ON embeddings 
USING hnsw (embedding vector_cosine_ops);
```

HNSW (Hierarchical Navigable Small World) provides:
- O(log N) search complexity
- High recall with configurable trade-offs
- Efficient for 384-dimensional embeddings

## Environment Variables

### Application Runtime

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `EMBEDDING_MODEL_NAME` | No | Defaults to `sentence-transformers/all-MiniLM-L6-v2` |
| `RAG_TOP_K` | No | Number of chunks to retrieve (default: 3) |
| `CONF_THRESHOLD` | No | Confidence threshold for answers (default: 0.6) |

### Ingestion Script

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `EMBEDDING_MODEL_NAME` | No | Model for generating embeddings |
| `INPUT_DATASET` | No | Fallback if `--input` not provided |

**Removed**:
- `VECTORSTORE_DIR` (no longer used)

## Testing

### Unit Tests

Tests use mocked database connections via `conftest.py`:
```python
@pytest.fixture(autouse=True)
def mock_database_operations(monkeypatch):
    """Mock psycopg2 database operations for all tests."""
    mock_conn = MagicMock()
    mock_conn.encoding = 'UTF8'
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=None)
    
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=None)
    mock_conn.cursor.return_value = mock_cursor
    
    mock_connect = MagicMock(return_value=mock_conn)
    monkeypatch.setattr("psycopg2.connect", mock_connect)
    monkeypatch.setattr("psycopg2.extras.execute_values", MagicMock())
```

Run tests:
```bash
pytest tests/
```

### Integration Testing

1. Deploy to dev environment
2. Ingest sample data via Kubernetes Job:
```bash
kubectl apply -f ingest-job.yaml -n dosm-dev
kubectl wait --for=condition=complete job/rag-ingest-sample -n dosm-dev --timeout=5m
kubectl logs job/rag-ingest-sample -n dosm-dev
```

3. Test predict endpoint:
```bash
kubectl run test-predict -n dosm-dev --rm -i --restart=Never --image=curlimages/curl:latest -- \
  curl -X POST http://faq-chatbot-dosm-insights:80/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key" \
  -d '{"query":"what is CPI for 2023?"}' \
  --max-time 90
```

Expected response:
```json
{
  "prediction": {
    "answer": "Grounded answer (rows 0–4): year=2023, indicator=CPI, value=121.0...",
    "citations": [{
      "source": "dosm_dataset",
      "snippet": "year=2023 indicator=CPI value=121.0...",
      "page_or_row": 0
    }],
    "confidence": 0.64,
    "failure_mode": null
  },
  "latency_ms": 26371,
  "model_version": "dosm-rag-bc11222"
}
```

**Note**: First request takes ~26-30 seconds due to model download. Subsequent requests are much faster (~200-500ms).

4. Verify database state:
```bash
PGPASSWORD='YourPassword' psql \
  -h pg-dosm.postgres.database.azure.com \
  -U dosm_admin \
  -d dosm-faq-chatbot-dev-postgres \
  -c "SELECT COUNT(*), MAX(created_at) FROM embeddings;"
```

### Performance Validation

Monitor:
- Query latency (should remain < 200ms for k=3)
- Database connection pool usage
- HNSW index hit rate
- Memory consumption (reduced without Chroma in-memory store)

## Rollback Procedure

If issues arise, rollback is straightforward:

1. Revert code changes (git revert to commit before migration)
2. Rebuild Docker image with artifacts COPY
3. Redeploy previous Helm chart version
4. Keep PostgreSQL migration in place (no harm)

## Future Enhancements

- **Incremental Updates**: Add upsert logic to update changed chunks only
- **Multi-Tenancy**: Add tenant_id column for isolated datasets
- **Versioning**: Track embedding model versions and migrate on model upgrades
- **Monitoring**: Add pgvector-specific metrics (index size, query latency)
- **Partitioning**: Partition embeddings table by dataset source for very large deployments

## References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [LangChain Postgres Integration](https://python.langchain.com/docs/integrations/vectorstores/pgvector)
- [PostgreSQL Flexible Server - Azure](https://docs.microsoft.com/azure/postgresql/flexible-server/)
