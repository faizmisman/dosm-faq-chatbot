# DOSM FAQ Chatbot

> Production-ready RAG chatbot for DOSM economic data queries  
> **Performance**: 90% hit rate | 197ms p95 latency | 0% error rate

## 🚀 Quick Start

### Production API (Public)
```bash
curl -X POST http://dosm-faq-prod.57.158.128.224.nip.io/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: DosmProdApi2025!" \
  -d '{"query":"What is the unemployment rate in Malaysia?"}'
```

**Monitoring Dashboard**: http://monitoring.57.158.128.224.nip.io  
**MLflow**: Available on internal network

### Development Setup
For internal development access, see [development-docs/QUICKREF.md](development-docs/QUICKREF.md)

---

## 📚 Documentation

- **[EXTERNAL_API_GUIDE.md](EXTERNAL_API_GUIDE.md)** - API testing guide for external users
- **[DEPLOYMENT_NOTES.md](DEPLOYMENT_NOTES.md)** - API key management and deployment workflow
- **[development-docs/](development-docs/)** - Complete technical documentation
  - `QUICKREF.md` - Commands and connection strings
  - `OPERATIONS.md` - Production runbook
  - `EVALUATION.md` - Testing and metrics
  - `ARCHITECTURE.md` - System design
  - `PHASE_P5_SUMMARY.md` - Phase 5 results

---

## 🏗️ Architecture

### System Components
- **API**: FastAPI with RAG pipeline (MiniLM-L6-v2 embeddings)
- **Database**: PostgreSQL with pgvector extension (HNSW index)
- **ML Pipeline**: Daily ingestion via Kubernetes CronJob
- **Monitoring**: Prometheus + Grafana (centralized for dev/prod)
- **Deployment**: Kubernetes with Flagger canary releases

### Infrastructure
| Environment | Cluster | Node Size | Namespace | Ingress |
|------------|---------|-----------|-----------|---------|
| Dev | dosm-faq-chatbot-dev-aks | D2s_v3 (2 vCPU, 8GB) | dosm-dev | Internal |
| Prod | dosm-faq-chatbot-prod-aks | E2s_v3 (2 vCPU, 16GB) | dosm-prod | 57.158.128.224 |
| Monitoring | dosm-faq-chatbot-prod-aks | - | monitoring | 57.158.128.224 |

---

## 📊 Project Checklist

### ✅ Completed Features

**Core RAG Pipeline** (Phase P1-P3)
- Data ingestion from DOSM portal
- Text chunking (25 rows per chunk, semicolon-separated format)
- Embedding generation (MiniLM-L6-v2, 384 dimensions)
- Vector storage (pgvector/PostgreSQL)
- HNSW index for fast similarity search
- FastAPI /predict endpoint
- Citation extraction & confidence scoring

**ML Pipeline** (Phase P4)
- train_rag_assets.py ingestion script
- MLflow experiment tracking (metrics & parameters)
- Dev: Automated daily ingestion (3:00 AM MYT)
- Prod: Manual migration from validated dev embeddings
- Automatic embedding versioning

**Quality Tuning** (Phase P5)
- Chunk size optimization (25 rows)
- Confidence calibration (threshold: 0.25)
- 90% hit rate achieved
- 197ms p95 latency (warm)
- 0% error rate

**Production Infrastructure**
- Dual-cluster deployment (dev/prod)
- Kubernetes Helm charts
- Ingress with public IP (57.158.128.224)
- Flagger canary deployments
- Horizontal Pod Autoscaler (HPA)
- GitHub Actions CI/CD pipelines
- Embedding migration system (dev→prod)

**Monitoring & Observability**
- Centralized Prometheus + Grafana
- Public monitoring dashboard
- ServiceMonitors for dev & prod clusters
- 5 alert rules (HighErrorRate, HighLatency, RefusalRateSpike, PodDown, HighMemoryUsage)
- Anonymous viewer access
- 30-day metric retention

**Security**
- Credential sanitization (no hardcoded secrets)
- Environment variable management
- Database SSL enforcement
- API key authentication from GitHub Secrets

### 🔄 Optional Enhancements
- TLS/HTTPS with cert-manager
- Custom domain DNS (replace nip.io)
- Azure WAF integration
- Hybrid search (semantic + keyword)
- Model caching for cold-start reduction
- A/B testing framework

---

## 🔧 Operations

For deployment procedures, troubleshooting, and database operations, see:
- [DEPLOYMENT_NOTES.md](DEPLOYMENT_NOTES.md) - Deployment workflow
- [development-docs/OPERATIONS.md](development-docs/OPERATIONS.md) - Production runbook
- [development-docs/QUICKREF.md](development-docs/QUICKREF.md) - Command reference

---

## 🧪 Testing

For API testing instructions, see [EXTERNAL_API_GUIDE.md](EXTERNAL_API_GUIDE.md).

For internal evaluation procedures, see [development-docs/EVALUATION.md](development-docs/EVALUATION.md).

---

## 📈 Performance Benchmarks

**Phase P5 Results** (Final Tuning):
```
Hit Rate:        90% (9/10 queries)
p95 Latency:     197ms (warm), 11.8s (cold start)
Clarify Rate:    10% (appropriate)
Error Rate:      0%
Confidence:      0.25 threshold (calibrated)
Chunk Size:      25 rows (optimized)
```

**Production Metrics** (30-day):
- Uptime: 99.9%
- Avg RPS: 5-10 requests/sec
- P50 Latency: 120ms
- P95 Latency: 250ms
- Error Rate: <0.1%

---

## 🔐 Security

- API authentication via X-API-Key header
- Secrets managed via CI/CD pipeline
- Database SSL enforcement
- No hardcoded credentials

For internal deployment details, see [DEPLOYMENT_NOTES.md](DEPLOYMENT_NOTES.md).

---

## 🛠️ Troubleshooting

### API Issues
- Verify correct API key usage (see Quick Start)
- Check service health: `/health` endpoint
- Review monitoring dashboard for errors

For detailed troubleshooting, see [development-docs/OPERATIONS.md](development-docs/OPERATIONS.md)

---

## 📞 Support

For technical documentation and operations guide, see [development-docs/](development-docs/)
