# Local Testing & Image Build

This doc covers two paths:
1. Local Docker build & push for iterative development (Option A).
2. Automated CI build & push via GitHub Actions (Option B).

---
## Option A: Local Build (Developer Machine)
Prereqs:
- Docker Desktop running
- Logged in to Azure (`az login`)
- ACR admin enabled (already true) or OIDC + `az acr login` permission

### 1. Login to ACR
```bash
ACR_NAME=dosmfaqchatbotacr1lw5a
az acr login -n $ACR_NAME
```

### 2. Build & Tag
Your runtime expects `dosm-faq-chatbot` repo name; CI also builds `dosm-insights-api` for backwards compatibility.
```bash
docker build -t $ACR_NAME.azurecr.io/dosm-faq-chatbot:dev -t $ACR_NAME.azurecr.io/dosm-insights-api:dev .
```

### 3. Push
```bash
docker push $ACR_NAME.azurecr.io/dosm-faq-chatbot:dev
docker push $ACR_NAME.azurecr.io/dosm-insights-api:dev
```

### 4. Deploy updated tag
```bash
helm upgrade --install faq-chatbot ./deploy/helm \
  -n dosm-dev \
  -f deploy/helm/values-dev.yaml \
  --set secrets.enabled=false \
  --set env.API_KEY_SECRET=app-secrets \
  --set env.API_KEY_KEY=API_KEY \
  --set env.DB.URL_SECRET=app-secrets \
  --set env.DB.URL_KEY=DATABASE_URL \
  --set image.repository="$ACR_NAME.azurecr.io/dosm-faq-chatbot" \
  --set image.tag=dev
```

### 5. Smoke Test
```bash
make smoke-dev
```
If port-forward fails, confirm pod status:
```bash
kubectl get pods -n dosm-dev
```
Ensure status is `Running` not `ImagePullBackOff`.

### 6. Rapid Iteration
Use `--build-arg` if you introduce build-time parameters later, e.g. model assets.
```bash
docker build --build-arg MODEL_VERSION=dosm-rag-dev -t $ACR_NAME.azurecr.io/dosm-faq-chatbot:dev .
```

---
## Option B: CI Build (GitHub Actions)
The workflow `.github/workflows/ci.yml` runs on pushes and PRs to `main`.
It performs:
1. Checkout & Python tests.
2. Docker build (both image names).
3. Azure OIDC login (requires repo secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `ACR_NAME`).
4. Push images: `dosm-insights-api:<SHA>` and `dosm-faq-chatbot:<SHA>`.
5. Upload artifacts with exact image tags.

### Required GitHub Secrets
- `AZURE_CLIENT_ID`: Federated identity client id (Service Principal or Managed Identity).
- `AZURE_TENANT_ID`: Tenant.
- `AZURE_SUBSCRIPTION_ID`: Subscription id.
- `ACR_NAME`: e.g. `dosmfaqchatbotacr1lw5a`.

### Adding OIDC Federated Credential
In Azure Portal or CLI, create SP and federated credential binding for your repo:
```bash
az ad sp create-for-rbac --name dosm-faq-chatbot-ci --role AcrPush --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/<platform-rg>/providers/Microsoft.ContainerRegistry/registries/$ACR_NAME --query appId -o tsv
```
Then configure federated identity (Portal: Security > Federated credentials) with:
- Subject: `repo:faizmisman/dosm-faq-chatbot:ref:refs/heads/main`

### Example Manual Trigger (re-run CI)
Push a commit or dispatch workflow:
```bash
gh workflow run CI
```

### Consuming Image Tag in Deploy Workflow
`deploy-dev.yml` can download artifact `image-tags` and set `image.tag` automatically. Example snippet:
```yaml
- uses: actions/download-artifact@v4
  with:
    name: image-tags
- name: Set IMAGE_TAG env
  run: echo "FAQ_IMAGE=$(cat faq-image-tag.txt)" >> $GITHUB_ENV
```
Then pass `--set image.repository` and `--set image.tag` derived from split of the tag string.

---
## Troubleshooting
| Symptom | Cause | Fix |
|---------|-------|-----|
| `ImagePullBackOff` | Image missing in ACR | Build & push locally or wait for CI |
| 401 Unauthorized pull | Missing AcrPull role | Assign AcrPull to AKS managed identity or enable admin & use pull secret |
| Port-forward timeout | Pod not Ready | Check logs, describe pod, ensure image is valid |
| CI OIDC login fails | Missing federated credential | Add repo branch subject to SP |

---
## Future Enhancements
- Multi-stage Docker build with separate runtime image.
- SBOM generation (`syft`) and vulnerability scan (`trivy`) in CI.
- Canary deploy workflow referencing new tag, auto rollback on failed smoke tests.

---
## Reference Commands Cheat Sheet
```bash
# List repos in ACR
az acr repository list -n $ACR_NAME -o table

# Show tags for a repository
az acr repository show-tags -n $ACR_NAME --repository dosm-faq-chatbot -o table

# Restart deployment after new image
kubectl rollout restart deployment/faq-chatbot-dosm-insights -n dosm-dev

# Get current image in pods
kubectl get pods -n dosm-dev -o jsonpath='{.items[0].spec.containers[0].image}'
```
