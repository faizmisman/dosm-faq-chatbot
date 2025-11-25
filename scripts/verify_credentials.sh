#!/bin/bash
# Credential Flow Verification Script
# Tests that all deployment contexts can access credentials properly

set -e

echo "=================================================="
echo "Credential Flow Verification"
echo "=================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
}

check_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
}

check_warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

# Test 1: Local .env file
echo "Test 1: Local .env file"
echo "------------------------"
if [ -f .env ]; then
    if grep -q "URL_ENCODED_PASSWORD=" .env && ! grep -q "<YOUR-" .env; then
        check_pass "Local .env exists with actual credentials"
        source .env
        if [ -n "$URL_ENCODED_PASSWORD" ] && [ -n "$DATABASE_URL" ]; then
            check_pass "Environment variables loaded from .env"
        else
            check_fail "Environment variables not properly set in .env"
        fi
    else
        check_fail "Local .env has placeholders, not actual credentials"
    fi
else
    check_warn "Local .env not found (create from .env.example for local dev)"
fi
echo ""

# Test 2: .env.example template
echo "Test 2: .env.example template"
echo "------------------------------"
if [ -f .env.example ]; then
    if grep -q "<YOUR-DB-PASSWORD>" .env.example; then
        check_pass ".env.example exists with placeholders (correct)"
    else
        check_warn ".env.example might contain real credentials (should use placeholders)"
    fi
else
    check_fail ".env.example template missing"
fi
echo ""

# Test 3: GitHub Secrets (can only verify locally configured)
echo "Test 3: GitHub Secrets Configuration"
echo "-------------------------------------"
if command -v gh &> /dev/null; then
    if gh auth status &> /dev/null; then
        SECRETS=$(gh secret list 2>&1)
        if echo "$SECRETS" | grep -q "URL_ENCODED_PASSWORD"; then
            check_pass "GitHub Secret 'URL_ENCODED_PASSWORD' is configured"
        else
            check_warn "GitHub Secret 'URL_ENCODED_PASSWORD' not found (required for CI/CD)"
        fi
        if echo "$SECRETS" | grep -q "PROD_API_KEY"; then
            check_pass "GitHub Secret 'PROD_API_KEY' is configured"
        else
            check_warn "GitHub Secret 'PROD_API_KEY' not found (optional for migration workflow)"
        fi
    else
        check_warn "GitHub CLI not authenticated (run: gh auth login)"
    fi
else
    check_warn "GitHub CLI (gh) not installed (cannot verify GitHub Secrets)"
fi
echo ""

# Test 4: Kubernetes Secrets
echo "Test 4: Kubernetes Secrets"
echo "--------------------------"
if command -v kubectl &> /dev/null; then
    # Check dev namespace
    if kubectl get namespace dosm-dev &> /dev/null; then
        if kubectl get secret database-secrets -n dosm-dev &> /dev/null; then
            check_pass "Kubernetes Secret 'database-secrets' exists in dosm-dev"
            # Verify it has the DATABASE_URL key
            if kubectl get secret database-secrets -n dosm-dev -o jsonpath='{.data.DATABASE_URL}' | base64 -d | grep -q "postgresql://"; then
                check_pass "Secret contains valid DATABASE_URL"
            else
                check_fail "Secret missing DATABASE_URL key"
            fi
        else
            check_warn "Kubernetes Secret 'database-secrets' not found in dosm-dev"
        fi
    else
        check_warn "Kubernetes namespace 'dosm-dev' not found"
    fi
    
    # Check prod namespace
    if kubectl get namespace dosm-prod &> /dev/null; then
        if kubectl get secret database-secrets -n dosm-prod &> /dev/null; then
            check_pass "Kubernetes Secret 'database-secrets' exists in dosm-prod"
            if kubectl get secret database-secrets -n dosm-prod -o jsonpath='{.data.DATABASE_URL}' | base64 -d | grep -q "postgresql://"; then
                check_pass "Secret contains valid DATABASE_URL"
            else
                check_fail "Secret missing DATABASE_URL key"
            fi
        else
            check_warn "Kubernetes Secret 'database-secrets' not found in dosm-prod"
        fi
    else
        check_warn "Kubernetes namespace 'dosm-prod' not found"
    fi
else
    check_warn "kubectl not installed (cannot verify Kubernetes secrets)"
fi
echo ""

# Test 5: No hardcoded credentials in Git-tracked files
echo "Test 5: Git-tracked files (security check)"
echo "-------------------------------------------"
TRACKED_FILES=$(git ls-files 2>/dev/null || echo "")
if [ -n "$TRACKED_FILES" ]; then
    # Check for common password patterns (case-insensitive)
    SUSPICIOUS_PATTERNS=(
        "Kusanagi@2105"
        "Kusanagi%402105"
        "password.*=.*[^<].*[^>].*[^Y].*[^O].*[^U].*[^R]" # password=something (but not placeholders)
    )
    
    FOUND_ISSUES=0
    for pattern in "${SUSPICIOUS_PATTERNS[@]}"; do
        if echo "$TRACKED_FILES" | xargs grep -l "$pattern" 2>/dev/null | grep -v ".sh$"; then
            check_fail "Found potential hardcoded credentials in tracked files"
            FOUND_ISSUES=1
            break
        fi
    done
    
    if [ $FOUND_ISSUES -eq 0 ]; then
        check_pass "No hardcoded credentials found in Git-tracked files"
    fi
else
    check_warn "Not in a Git repository"
fi
echo ""

# Test 6: Python scripts use os.getenv()
echo "Test 6: Python scripts use environment variables"
echo "-------------------------------------------------"
if grep -r "os.getenv('DATABASE_URL')" scripts/*.py &> /dev/null; then
    check_pass "Python scripts use os.getenv() for DATABASE_URL"
else
    check_warn "Python scripts might not be using environment variables"
fi

if grep -r "os.getenv('URL_ENCODED_PASSWORD')" scripts/*.py &> /dev/null; then
    check_pass "Python scripts use os.getenv() for passwords"
else
    check_warn "Python scripts might not be using environment variables for passwords"
fi
echo ""

# Test 7: Workflow files use GitHub Secrets
echo "Test 7: GitHub Actions workflows use secrets"
echo "---------------------------------------------"
if grep -r "\${{ secrets\." .github/workflows/*.yml &> /dev/null; then
    check_pass "GitHub Actions workflows use GitHub Secrets"
    
    # Count unique secrets used
    SECRET_COUNT=$(grep -roh "\${{ secrets\.[A-Z_]* }}" .github/workflows/*.yml | sort -u | wc -l | tr -d ' ')
    check_pass "Found $SECRET_COUNT unique secrets referenced in workflows"
else
    check_fail "GitHub Actions workflows not using secrets (security risk)"
fi
echo ""

# Test 8: K8s manifests use secretKeyRef
echo "Test 8: Kubernetes manifests use secretKeyRef"
echo "----------------------------------------------"
if grep -r "secretKeyRef:" deploy/k8s/*.yml &> /dev/null; then
    check_pass "Kubernetes manifests use secretKeyRef for sensitive data"
else
    check_warn "Kubernetes manifests might not be using secretKeyRef"
fi
echo ""

# Summary
echo "=================================================="
echo "Summary"
echo "=================================================="
echo ""
echo "Deployment contexts:"
echo "  ✓ Local development: Use .env (gitignored)"
echo "  ✓ GitHub Actions: Use GitHub Secrets"
echo "  ✓ Kubernetes: Use Kubernetes Secrets"
echo "  ✓ Git repository: Only placeholders, no real credentials"
echo ""
echo "For detailed credential flow documentation, see:"
echo "  development-docs/CREDENTIAL_FLOW.md"
echo "  SECURITY.md"
echo ""
echo "To set up credentials:"
echo "  Local: cp .env.example .env && vim .env"
echo "  GitHub: gh secret set URL_ENCODED_PASSWORD --body \"your-password\""
echo "  K8s: kubectl create secret generic database-secrets --from-literal=DATABASE_URL=\"...\""
echo ""
