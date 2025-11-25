# NGINX Ingress Controller Setup

This document describes the NGINX Ingress Controller configuration for the production cluster.

## Overview

The NGINX Ingress Controller enables external HTTP/HTTPS access to services running in the Kubernetes cluster via a single Azure LoadBalancer with a public IP.

**Current Configuration:**
- **Public IP**: `57.158.128.224`
- **Public Endpoint**: `http://dosm-faq-prod.57.158.128.224.nip.io`
- **Namespace**: `ingress-nginx`
- **Helm Chart**: `ingress-nginx/ingress-nginx`

## Architecture

```
Internet
   ↓
Azure LoadBalancer (57.158.128.224)
   ↓
NGINX Ingress Controller (Pod)
   ↓
Ingress Rules (routing based on hostname/path)
   ↓
Kubernetes Services
   ↓
Application Pods
```

## Installation

### Prerequisites

1. **Add Helm repository**:
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

2. **Connect to production cluster**:
```bash
az aks get-credentials \
  --resource-group dosm-faq-chatbot-prod-rg \
  --name dosm-faq-chatbot-prod-aks
```

### Install

```bash
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --values deploy/k8s/nginx-ingress-values.yaml \
  --wait --timeout=5m
```

### Verify Installation

```bash
# Check pods
kubectl get pods -n ingress-nginx

# Check service and external IP
kubectl get svc -n ingress-nginx ingress-nginx-controller

# Check logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=50
```

## Configuration

### Key Settings

1. **LoadBalancer with Existing IP**:
   - Reuses the existing Azure public IP created by AKS
   - Annotation: `service.beta.kubernetes.io/azure-pip-name: "kubernetes-aa6aa929cf0a8499c9f9c213dece98a3"`

2. **Minimal Resources**:
   - Requests: 50m CPU, 128Mi memory
   - Limits: 200m CPU, 256Mi memory
   - Optimized for small production cluster

3. **Prometheus Metrics**:
   - Enabled for monitoring
   - Endpoint: `http://<controller-pod>:10254/metrics`

4. **Traffic Policy**:
   - `externalTrafficPolicy: Local` - preserves client source IPs

### Configuration File

See [`nginx-ingress-values.yaml`](./nginx-ingress-values.yaml) for full configuration.

## Usage

### Create an Ingress Resource

Ingress resources define routing rules for your applications:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  namespace: dosm-prod
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "4m"
spec:
  ingressClassName: nginx
  rules:
    - host: my-app.57.158.128.224.nip.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-app-service
                port:
                  number: 80
```

### Test Access

```bash
# Using nip.io DNS (automatic)
curl http://dosm-faq-prod.57.158.128.224.nip.io/health

# Using IP directly with Host header
curl -H "Host: dosm-faq-prod.57.158.128.224.nip.io" http://57.158.128.224/health
```

## Troubleshooting

### LoadBalancer IP Stuck in Pending

**Symptoms**: External IP shows `<pending>` for several minutes

**Causes**:
- Insufficient CPU resources on cluster nodes
- Azure quota limits
- Cloud provider errors

**Solutions**:
```bash
# Check events
kubectl describe svc -n ingress-nginx ingress-nginx-controller | grep -A 10 "Events:"

# Scale down other workloads to free resources
kubectl scale deployment <deployment> --replicas=0 -n dosm-prod

# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources:"
```

### Ingress Rules Not Working

**Symptoms**: 404 errors or ingress not routing traffic

**Checks**:
```bash
# Verify ingress resource exists
kubectl get ingress -A

# Check ingress details
kubectl describe ingress <name> -n <namespace>

# Verify ingressClassName matches
kubectl get ingress <name> -n <namespace> -o yaml | grep ingressClassName

# Check controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller --tail=100
```

### Backend Service Not Found

**Symptoms**: `503 Service Temporarily Unavailable`

**Checks**:
```bash
# Verify service exists
kubectl get svc -n <namespace>

# Verify pods are running
kubectl get pods -n <namespace>

# Check service endpoints
kubectl get endpoints <service-name> -n <namespace>
```

### SSL/TLS Certificate Issues

**Note**: Current setup uses HTTP only. For HTTPS:

1. **Install cert-manager**:
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

2. **Add TLS to Ingress**:
```yaml
spec:
  tls:
    - hosts:
        - your-domain.com
      secretName: tls-secret
  rules:
    - host: your-domain.com
      # ...
```

## Monitoring

### Check Ingress Controller Metrics

```bash
# Port-forward to metrics endpoint
kubectl port-forward -n ingress-nginx deployment/ingress-nginx-controller 10254:10254

# View metrics
curl http://localhost:10254/metrics
```

### Key Metrics

- `nginx_ingress_controller_requests` - Request count by status
- `nginx_ingress_controller_request_duration_seconds` - Request latency
- `nginx_ingress_controller_bytes_sent` - Bytes sent to clients

## Maintenance

### Upgrade Ingress Controller

```bash
# Update Helm repo
helm repo update

# Check available versions
helm search repo ingress-nginx

# Upgrade
helm upgrade ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --values deploy/k8s/nginx-ingress-values.yaml \
  --wait --timeout=5m
```

### Rollback

```bash
# List releases
helm history ingress-nginx -n ingress-nginx

# Rollback to previous version
helm rollback ingress-nginx <revision> -n ingress-nginx
```

### Uninstall

```bash
# Delete Helm release
helm uninstall ingress-nginx -n ingress-nginx

# Delete namespace
kubectl delete namespace ingress-nginx

# Note: Azure LoadBalancer public IP will be released
```

## Cost Considerations

- **LoadBalancer**: ~$5-10/month (Azure Standard Public IP + Load Balancer rules)
- **Resources**: Minimal (50m CPU, 128Mi RAM)
- **Alternative**: Use NodePort + Azure Application Gateway (more expensive but more features)

## Future Enhancements

1. **Custom Domain**: Replace nip.io with real domain
   - Register domain
   - Configure Azure DNS zone
   - Update ingress.host in values

2. **HTTPS/TLS**: Install cert-manager for automatic SSL certificates
   - Use Let's Encrypt for free certs
   - Auto-renewal every 90 days

3. **Rate Limiting**: Add annotations for DDoS protection
   ```yaml
   nginx.ingress.kubernetes.io/limit-rps: "10"
   ```

4. **Authentication**: Add basic auth or OAuth2 proxy
   ```yaml
   nginx.ingress.kubernetes.io/auth-type: basic
   nginx.ingress.kubernetes.io/auth-secret: basic-auth
   ```

5. **WAF**: Integrate with Azure Application Gateway for Web Application Firewall

## References

- [NGINX Ingress Controller Docs](https://kubernetes.github.io/ingress-nginx/)
- [Helm Chart Values](https://github.com/kubernetes/ingress-nginx/tree/main/charts/ingress-nginx)
- [Azure LoadBalancer Integration](https://cloud-provider-azure.sigs.k8s.io/topics/loadbalancer/)
- [nip.io Wildcard DNS](https://nip.io/)
