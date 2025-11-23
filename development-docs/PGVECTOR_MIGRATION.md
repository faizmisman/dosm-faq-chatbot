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

1. Run migration on dev/prod databases:
```bash
# Dev
az postgres flexible-server execute \
  --name dosm-faq-chatbot-dev-postgres \
  --admin-user adminuser \
  --database-name dosm_dev \
  --file-path sql/migrations/002_vector_store.sql

# Prod
az postgres flexible-server execute \
  --name dosm-faq-chatbot-prod-postgres \
  --admin-user adminuser \
  --database-name dosm_prod \
  --file-path sql/migrations/002_vector_store.sql
```

2. Ensure DATABASE_URL is in Key Vault and available via secret:
```yaml
# Helm values already configured with:
secrets:
  enabled: true
  # DATABASE_URL comes from external secret or Key Vault CSI
```

3. Enable ingestion Job to populate database:
```yaml
ragIngest:
  enabled: true  # Run once on deploy
```

4. Deploy via GitHub Actions workflow or manual helm upgrade:
```bash
helm upgrade --install faq-chatbot-dosm-insights ./deploy/helm \
  -f deploy/helm/values-dev.yaml \
  --set image.tag=$IMAGE_TAG
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

Tests in `tests/test_rag_pipeline.py` still work but require:
```python
# conftest.py or test setup
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
```

### Integration Testing

1. Populate test database with sample data
2. Query `/predict` endpoint
3. Verify embeddings retrieved from PostgreSQL
4. Check response citations and confidence scores

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
