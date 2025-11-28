# Local Kubernetes Testing Guide

This guide helps you test the DOSM FAQ Chatbot on your **local Docker Desktop Kubernetes cluster only**.

**⚠️ Important**: This setup uses local Docker images and does NOT push to any remote registry (Azure ACR). All testing stays on your machine.

## Prerequisites

- Docker Desktop with Kubernetes enabled
- kubectl configured with `docker-desktop` context
- Helm 3 installed
- PostgreSQL database accessible from your local machine (optional for full testing)

## Quick Start

### 1. Deploy to Local Kubernetes

```bash
# One command deployment (builds image, creates namespace, deploys Helm chart)
make -f Makefile.local deploy
```

This will:
- Switch to `docker-desktop` context (local only)
- Create `dosm-local` namespace
- Build Docker image tagged as `dosm-faq-chatbot:local` (stays on your machine)
- Create secrets from `.env` file (API_KEY and DATABASE_URL)
- Deploy using Helm with local configuration
- Expose service on NodePort 30080 (localhost only)

**Note**: The image is built locally with `pullPolicy: Never` - Kubernetes will NOT attempt to pull from any remote registry.

**Secrets**: API key and database URL are automatically read from your `.env` file.

### 2. Test the API

```bash
# Health check
curl http://localhost:30080/health

# Test prediction (smoke test)
make smoke-local

# Or manually:
curl -X POST http://localhost:30080/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-test-key" \
  -d '{"query":"What is the unemployment rate?"}'
```

### 3. View Logs

```bash
# Follow logs in real-time
make -f Makefile.local logs

# Or manually:
kubectl logs -n dosm-local -l app=faq-chatbot-dosm-insights -f
```

### 4. Check Status

```bash
make -f Makefile.local status
```

## Configuration

### Local Values File

Configuration is in `deploy/helm/values-local.yaml`:

```yaml
image:
  repository: dosm-faq-chatbot
  tag: local
  pullPolicy: Never  # NEVER pull from remote - use local image only
  pullSecretName: ""  # No registry credentials needed

service:
  type: NodePort
  nodePort: 30080  # Access via localhost:30080 only

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### Database Configuration

Database connection is automatically read from your `.env` file:

```bash
# Your .env should have:
DATABASE_URL="postgresql://user:password@host:5432/dbname?sslmode=require"
```

The `make local-deploy` command will automatically create the `local-db-url` secret from this value.

### API Key

API key is automatically read from your `.env` file:

```bash
# Your .env should have:
API_KEY="your-api-key-here"
```

To manually update secrets after deployment:

```bash
# Update API key
kubectl create secret generic local-api-key \
  --from-literal=API_KEY="new-key" \
  -n dosm-local --dry-run=client -o yaml | kubectl apply -f -

# Update database URL
kubectl create secret generic local-db-url \
  --from-literal=DATABASE_URL="postgresql://..." \
  -n dosm-local --dry-run=client -o yaml | kubectl apply -f -

# Restart deployment to pick up new secrets
make local-restart
```

## Common Operations

### Stop and Start

```bash
# Stop all local services and clean up
make -f Makefile.local clean

# Restart from scratch
make -f Makefile.local deploy
```

### Rebuild and Redeploy

```bash
# Rebuild image and redeploy
make -f Makefile.local deploy
```

### Restart Pods

```bash
# Restart without rebuilding
make -f Makefile.local restart
```

### View Kubernetes Resources

```bash
# Pods
kubectl get pods -n dosm-local

# Services
kubectl get svc -n dosm-local

# Deployments
kubectl get deployments -n dosm-local

# Secrets
kubectl get secrets -n dosm-local
```

### Stop Local Server

```bash
# Stop and remove all local resources (recommended when done testing)
make -f Makefile.local clean
```

This will:
- Uninstall the Helm release
- Delete the `dosm-local` namespace
- Remove all pods, services, and secrets
- Free up local resources

**Note**: You can always redeploy later with `make -f Makefile.local deploy`

## Testing RAG Ingestion

To test the ML pipeline locally:

1. Edit `deploy/helm/values-local.yaml`:
   ```yaml
   ragIngest:
     enabled: true
   ```

2. Redeploy:
   ```bash
   make -f Makefile.local deploy
   ```

3. Check job status:
   ```bash
   kubectl get jobs -n dosm-local
   kubectl logs -n dosm-local job/rag-ingest
   ```

## Differences from Cloud Deployment

| Feature | Cloud (Dev/Prod) | Local |
|---------|------------------|-------|
| Image Source | Azure ACR | Local Docker |
| Service Type | ClusterIP + Ingress | NodePort |
| Access | Ingress URL | localhost:30080 |
| Replicas | 1-10 (HPA) | 1 |
| Resources | 250m CPU, 512Mi RAM | 100m CPU, 256Mi RAM |
| Monitoring | Prometheus enabled | Disabled |
| Secrets | Azure Key Vault / K8s | K8s only |

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod -n dosm-local <pod-name>

# Check events
kubectl get events -n dosm-local --sort-by='.lastTimestamp'
```

### Image Pull Error

Make sure image is built locally:
```bash
docker images | grep dosm-faq-chatbot
# Should show: dosm-faq-chatbot  local
```

If missing:
```bash
make -f Makefile.local build
```

### Connection Refused

Check service is running:
```bash
kubectl get svc -n dosm-local
# Should show NodePort 30080

# Check pod logs
make local-logs
```

### Database Connection Issues

1. Ensure DATABASE_URL is correct:
   ```bash
   kubectl get secret local-db-url -n dosm-local -o jsonpath='{.data.DATABASE_URL}' | base64 -d
   ```

2. Test database connectivity from pod:
   ```bash
   kubectl exec -n dosm-local <pod-name> -- env | grep DATABASE_URL
   ```

3. For local PostgreSQL in Docker:
   ```bash
   # Start PostgreSQL container
   docker run --name dosm-postgres \
     -e POSTGRES_USER=dosm \
     -e POSTGRES_PASSWORD=localpass \
     -e POSTGRES_DB=dosm_local \
     -p 5432:5432 \
     -d pgvector/pgvector:pg16
   
   # Use this DATABASE_URL:
   # postgresql://dosm:localpass@host.docker.internal:5432/dosm_local
   ```

## Switch Back to Cloud

```bash
# Dev cluster
kubectl config use-context dosm-faq-chatbot-dev-aks

# Prod cluster  
kubectl config use-context dosm-faq-chatbot-prod-aks
```

## Makefile Commands Reference

| Command | Description |
|---------|-------------|
| `make -f Makefile.local deploy` | Build, setup, and deploy to local K8s |
| `make -f Makefile.local build` | Build Docker image only |
| `make -f Makefile.local setup` | Create namespace and switch context |
| `make -f Makefile.local secrets` | Create API key and DB secrets |
| `make -f Makefile.local logs` | Follow pod logs |
| `make -f Makefile.local status` | Show pods, services, and access URL |
| `make -f Makefile.local restart` | Restart deployment |
| `make -f Makefile.local clean` | Stop and remove all local resources |
| `make -f Makefile.local smoke` | Quick API test |
| `make -f Makefile.local help` | Show all available commands |

## Next Steps

1. **Test API endpoints** with different queries
2. **Load test database** with sample embeddings
3. **Try RAG ingestion** with local CSV files
4. **Debug issues** before deploying to dev/prod
5. **Iterate quickly** without cloud costs

**Tip**: Use `make -f Makefile.local help` to see all available commands

---

For cloud deployment, see [DEPLOYMENT_NOTES.md](DEPLOYMENT_NOTES.md)
