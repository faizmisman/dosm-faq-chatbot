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
