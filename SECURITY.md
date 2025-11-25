# Security Policy

## Sensitive Data Management

This repository contains **example configurations** for educational and deployment purposes. All sensitive credentials have been sanitized.

### 🔒 Credentials NOT to Commit

**NEVER** commit the following to this repository:

1. **Database Passwords**
   - PostgreSQL admin passwords
   - Connection strings with embedded passwords
   
2. **API Keys**
   - Dev/Prod API keys
   - Service account tokens
   
3. **Azure Credentials**
   - Subscription IDs
   - Tenant IDs
   - Service principal secrets
   
4. **Terraform State**
   - `terraform.tfstate` files (may contain secrets)
   - `*.tfvars` files with actual values

### ✅ How We Handle Secrets

#### For Local Development

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your actual credentials in `.env` (this file is git-ignored)

3. Use environment variables in your code:
   ```python
   import os
   db_password = os.getenv("DB_PASSWORD")
   ```

#### For Kubernetes Deployments

Secrets are managed via Kubernetes Secrets, **not** in code:

```bash
# Create secret (never commit this command with actual values)
kubectl create secret generic database-secrets -n dosm-dev \
  --from-literal=DATABASE_URL="postgresql://user:<password>@host:5432/db"
```

#### For Terraform

1. Create `terraform.tfvars` (git-ignored):
   ```hcl
   postgres_admin_password = "your-secure-password"
   ```

2. Or use environment variables:
   ```bash
   export TF_VAR_postgres_admin_password="your-secure-password"
   ```

### 📝 Documentation Placeholders

All documentation files use **placeholders** for sensitive values:

- `<your-db-password>` - Replace with actual database password
- `<your-dev-api-key>` - Replace with dev API key
- `<your-prod-api-key>` - Replace with prod API key
- `<url-encoded-password>` - URL-encoded version of password
- `<your-subscription-id>` - Azure subscription ID

### 🔍 Checking for Exposed Secrets

Before committing, scan for accidentally committed secrets:

```bash
# Check for common secret patterns
git grep -i "kusanagi"
git grep -i "password.*="
git grep -E "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

# Use git-secrets (recommended)
git secrets --scan
```

### 🚨 If Secrets Were Exposed

If you accidentally committed secrets:

1. **Immediately rotate** the exposed credentials
2. Remove from git history:
   ```bash
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch path/to/file' \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. Force push (coordinate with team):
   ```bash
   git push origin --force --all
   ```

### 📋 Secrets Checklist

Before deployment:

- [ ] All `.tfvars` files are git-ignored
- [ ] Kubernetes secrets created in correct namespaces
- [ ] `.env` file exists locally (not committed)
- [ ] Documentation uses placeholders only
- [ ] No hardcoded passwords in code
- [ ] API keys retrieved from secrets/environment
- [ ] Database URLs use secret references

### 🔗 External Secret Management

For production, consider using:

- **Azure Key Vault** - Centralized secret storage
- **Sealed Secrets** - Encrypted Kubernetes secrets
- **External Secrets Operator** - Sync from Key Vault to K8s

Example Key Vault integration:
```bash
# Store secret in Azure Key Vault
az keyvault secret set \
  --vault-name dosm-kv-prod \
  --name db-password \
  --value "your-secure-password"

# Reference in Kubernetes (with CSI driver)
# See deploy/helm/values-prod.yaml for example
```

### 📞 Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public issue
2. Email: [your-security-email]
3. Include: Description, impact, reproduction steps

### 🛡️ Best Practices

1. **Use Strong Passwords**
   - Min 16 characters
   - Mix of uppercase, lowercase, numbers, symbols
   - Unique per environment

2. **Rotate Regularly**
   - Database passwords: Every 90 days
   - API keys: Every 6 months
   - Service accounts: Yearly

3. **Principle of Least Privilege**
   - Dev environment: Read/write on dev database only
   - Prod environment: Separate credentials, audited access

4. **Audit Access**
   ```bash
   # Check who has access to secrets
   kubectl get secrets -n dosm-prod -o yaml | grep annotations
   ```

### 📚 Additional Resources

- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Azure Key Vault Best Practices](https://docs.microsoft.com/en-us/azure/key-vault/general/best-practices)
- [Kubernetes Secrets Management](https://kubernetes.io/docs/concepts/configuration/secret/)

---

**Remember**: Secrets in code = security breach. Always use environment variables or secret management systems.
