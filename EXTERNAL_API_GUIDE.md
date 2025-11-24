# DOSM FAQ Chatbot - External API Guide

## Quick Start

**Production API Endpoint**: `http://dosm-faq-prod.57.158.128.224.nip.io`

**API Key**: `prod-placeholder`

**Status**: ✅ Live and accessible from anywhere

---

## Test the API

### Health Check
```bash
curl http://dosm-faq-prod.57.158.128.224.nip.io/health
```

**Expected Response**:
```json
{
  "status": "ok",
  "version": "dosm-rag-main",
  "checks": {
    "db": "ok",
    "vector_store": "pending"
  }
}
```

### Query Example
```bash
curl -X POST http://dosm-faq-prod.57.158.128.224.nip.io/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: prod-placeholder" \
  -d '{"query":"What is the unemployment rate in Malaysia?"}'
```

**Expected Response**:
```json
{
  "prediction": {
    "answer": "Based on the data...",
    "citations": ["source_1"],
    "confidence": 0.85,
    "failure_mode": null
  },
  "latency_ms": 250,
  "model_version": "dosm-rag-main"
}
```

---

## Sample Queries

### Economic Indicators
```bash
# Employment statistics
curl -X POST http://dosm-faq-prod.57.158.128.224.nip.io/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: prod-placeholder" \
  -d '{"query":"employment rate 2024"}'

# Labour force participation
curl -X POST http://dosm-faq-prod.57.158.128.224.nip.io/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: prod-placeholder" \
  -d '{"query":"labour force participation rate by state"}'

# Industry employment
curl -X POST http://dosm-faq-prod.57.158.128.224.nip.io/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: prod-placeholder" \
  -d '{"query":"which industries have the most jobs?"}'
```

---

## API Response Schema

### Success Response
```json
{
  "prediction": {
    "answer": "string",           // Generated answer
    "citations": ["string"],      // Source references
    "confidence": 0.0-1.0,        // Confidence score
    "failure_mode": null          // null if successful
  },
  "latency_ms": number,           // Response time
  "model_version": "string"       // Model identifier
}
```

### Clarification Needed
```json
{
  "prediction": {
    "answer": "Could you clarify...",
    "citations": [],
    "confidence": 0.0,
    "failure_mode": "needs_clarification"
  },
  "latency_ms": number,
  "model_version": "string"
}
```

### Low Confidence / No Data
```json
{
  "prediction": {
    "answer": "No relevant data found.",
    "citations": [],
    "confidence": 0.0,
    "failure_mode": "low_confidence"
  },
  "latency_ms": number,
  "model_version": "string"
}
```

---

## Authentication

All requests require the `X-API-Key` header:

```bash
-H "X-API-Key: prod-placeholder"
```

**Note**: This is a test API key. For production use, request a dedicated API key.

---

## Rate Limits

- **No rate limits** currently enforced
- Recommended: Max 100 requests/minute for testing
- Production will have rate limiting enabled

---

## Technical Details

### Infrastructure
- **Hosting**: Azure Kubernetes Service (AKS)
- **Region**: Southeast Asia
- **Load Balancer**: Azure LB with public IP
- **Ingress**: NGINX Ingress Controller
- **DNS**: nip.io wildcard (*.57.158.128.224.nip.io → 57.158.128.224)

### Architecture
- **RAG System**: Retrieval-Augmented Generation
- **Embedding Model**: sentence-transformers/all-MiniLM-L6-v2
- **Vector Store**: PostgreSQL + pgvector extension
- **LLM Provider**: Configurable (OpenAI/Groq/local)

### Performance Benchmarks (Phase P5)
| Metric | Value |
|--------|-------|
| Hit Rate | 90% (9/10 queries successful) |
| p95 Latency (warm) | 197ms |
| p95 Latency (cold) | 11.8s |
| Clarification Rate | 10% |
| Error Rate | 0% |

---

## Support & Issues

### Reporting Issues
If you encounter problems:

1. **Check health endpoint**: `curl http://dosm-faq-prod.57.158.128.224.nip.io/health`
2. **Verify API key**: Ensure `X-API-Key: prod-placeholder` is included
3. **Check request format**: Content-Type must be `application/json`
4. **Report to**: faizmisman@example.com (or create GitHub issue)

### Common Issues

**Problem**: `{"detail":"Invalid or missing API key"}`  
**Solution**: Add header `-H "X-API-Key: prod-placeholder"`

**Problem**: `Connection refused`  
**Solution**: Check endpoint URL is `http://` not `https://` (SSL not configured)

**Problem**: `"No relevant data found"`  
**Solution**: Vector store may be empty. This is expected if embeddings haven't been loaded yet.

---

## Alternative Access Methods

### Direct IP (without DNS)
```bash
curl -X POST http://57.158.128.224/predict \
  -H "Content-Type: application/json" \
  -H "Host: dosm-faq-prod.57.158.128.224.nip.io" \
  -H "X-API-Key: prod-placeholder" \
  -d '{"query":"your question here"}'
```

### Using Postman
1. **Method**: POST
2. **URL**: `http://dosm-faq-prod.57.158.128.224.nip.io/predict`
3. **Headers**:
   - `Content-Type: application/json`
   - `X-API-Key: prod-placeholder`
4. **Body** (raw JSON):
   ```json
   {
     "query": "What is the unemployment rate?"
   }
   ```

### Using Python
```python
import requests

url = "http://dosm-faq-prod.57.158.128.224.nip.io/predict"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "prod-placeholder"
}
data = {
    "query": "What is the unemployment rate in Malaysia?"
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

---

## Changelog

### 2025-11-25
- ✅ Production ingress configured with NGINX
- ✅ Public LoadBalancer IP: 57.158.128.224
- ✅ nip.io DNS for easy access
- ✅ API endpoint live and tested
- ⚠️ Vector store pending data ingestion

---

## Next Steps

### For Testers
1. Test various query types (employment, economic data, clarifications)
2. Measure response times and accuracy
3. Report any unexpected behaviors or errors
4. Try edge cases (very long queries, special characters, etc.)

### For Developers
1. Custom domain setup (replace nip.io)
2. SSL/TLS certificate (Let's Encrypt)
3. Rate limiting configuration
4. Enhanced monitoring and logging
5. Load embeddings into vector store
