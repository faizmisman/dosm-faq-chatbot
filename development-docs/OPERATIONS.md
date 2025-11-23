# Operations Guide

## 1) Environments

- **Local**, **Dev (AKS)**, **Prod (AKS)**. Separate namespaces & DBs.

## 2) Deployments

- **Dev**: auto on merge to `main` (deploy‑dev.yml).  
- **Prod**: manual canary → promote (promote‑prod.yml).

Helm (manual example):

```bash
az aks get-credentials -g rg-dosm-insights-dev -n aks-dosm-dev
helm upgrade --install dosm-insights ./deploy/helm -f deploy/helm/values-dev.yaml --set image.tag=<git_sha>
```

## 2.1) Ingress & DNS (Dev)

### Install nginx ingress controller (LoadBalancer service)
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer \
  --set controller.ingressClassResource.name=nginx \
  --set controller.ingressClassResource.default=true
```

Wait for external IP:
```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller -w
```

### Verify application ingress
Your chart enables ingress when `ingress.enabled=true` (values-dev.yaml) and sets host placeholder.
```bash
kubectl get ingress -n dosm-dev
kubectl describe ingress faq-chatbot-dosm-insights -n dosm-dev
```

If ADDRESS column remains empty, the controller may not be ready or class mismatch; ensure `ingress.className: nginx` in values.

### DNS record
Create an `A` record pointing to the LoadBalancer external IP:
```
dosm-dev.example.com -> <EXTERNAL_IP>
```
If using Azure DNS:
```bash
az network dns record-set a add-record \
  --resource-group <dns-rg> \
  --zone-name <zone> \
  --record-set-name dosm-dev \
  --ipv4-address <EXTERNAL_IP>
```

### TLS (optional)
Install cert-manager:
```bash
helm repo add jetstack https://charts.jetstack.io
helm upgrade --install cert-manager jetstack/cert-manager \
  -n cert-manager --create-namespace \
  --set installCRDs=true
```
ClusterIssuer (Let’s Encrypt HTTP-01) example:
```bash
kubectl apply -f - <<'EOF'
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt
spec:
  acme:
    email: ops@example.com
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-account-key
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```
Then add to ingress annotations & TLS block (Helm values override):
```bash
--set ingress.tls.enabled=true \
--set ingress.tls.secretName=faq-chatbot-tls \
--set ingress.annotations.cert-manager\.io/cluster-issuer=letsencrypt
```

### Smoke test external endpoint
```bash
curl -H "X-API-Key: $(kubectl get secret app-secrets -n dosm-dev -o jsonpath='{.data.API_KEY}' | base64 -d)" \
  https://dosm-dev.example.com/predict \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is CPI?"}' | jq .
```

### Common ingress issues
| Symptom | Root Cause | Fix |
|---------|------------|-----|
| 404 from nginx default backend | Host mismatch or path not found | Check ingress host; curl with `-H Host:` header |
| Pending external IP | Cloud provider quota or delay | Recheck service type, watch events, ensure LoadBalancer allowed |
| TLS cert pending | ACME challenge not reachable | Verify DNS A record, check cert-manager pod logs |
| 502/503 | Pod failing readiness | `kubectl describe pod`, check logs, resource limits |

### Production notes
Use distinct domain (e.g. `faq.dosm.example.com`). Consider WAF, rate limiting annotations, and separate ingress class for internal endpoints.


## 3) Monitoring

- Prometheus scrapes `/metrics`; Grafana dashboard JSON checked‑in.  
- Alert ideas:
  - 5xx > 5% for 5 min
  - p95 > 1.5s for 10 min
  - refusal rate spike > baseline + 3σ

## 4) Logs & troubleshooting

- Structured JSON logs in Log Analytics. Include `request_id`, `model_version`, `latency_ms`.  
- Common issues:
  - **Healthz fails** → check vector store path & DB connectivity.
  - **High latency** → token limits, upstream LLM latency, pod CPU throttling.
  - **Frequent refusals** → embeddings stale; re‑run `train_rag_assets.py`.

## 5) Scaling & cost

- HPA min=2 max=10, target CPU 60–70%.  
- Start Postgres in burstable tier (B1ms).  
- Monitor LLM token spend (largest cost driver).

## 6) Rollback

```bash
helm history dosm-insights -n dosm-prod
helm rollback dosm-insights <rev> -n dosm-prod
# or
kubectl rollout undo deployment/dosm-insights-api -n dosm-prod
```

## 7) Security

- HTTPS ingress, API key/JWT, per‑key rate limits.  
- Secrets exclusively in Key Vault (MSI).  
- Principle of least privilege for identities.  
- Enforce TLS + strict host, add rate limit annotations (nginx) for `/predict`.
