# OpenShift Secrets Guide

## Understanding the Two Secrets

Your OpenShift deployment needs **two different secrets**:

### 1. docker-registry-secret (for pulling images)
- **Type**: `kubernetes.io/dockerconfigjson`
- **Purpose**: Authenticates with nvcr.io to pull NVIDIA container images
- **Used by**: `imagePullSecrets` in pod spec
- **Contains**: `.dockerconfigjson` with Docker credentials

### 2. ngc-api-key (for environment variable)
- **Type**: `Opaque`
- **Purpose**: Provides NGC_API_KEY as environment variable to containers
- **Used by**: `env` section in container spec
- **Contains**: `NGC_API_KEY` key-value pair

## Why Two Secrets?

```yaml
# Pod specification uses BOTH secrets:

spec:
  # Secret 1: For pulling the image
  imagePullSecrets:
    - name: docker-registry-secret  # Uses .dockerconfigjson
  
  containers:
  - name: training
    image: nvcr.io/nvidia/cugraph/financial-fraud-training:1.0.1
    
    # Secret 2: For environment variable
    env:
    - name: NGC_API_KEY
      valueFrom:
        secretKeyRef:
          name: ngc-api-key  # Uses NGC_API_KEY key
          key: NGC_API_KEY
```

## Scenario 1: You Already Have docker-registry-secret

If your OpenShift cluster already has the docker-registry-secret:

```bash
# Check if it exists
oc get secret docker-registry-secret -n fraud-detection

# Output shows:
# NAME                     TYPE                             DATA   AGE
# docker-registry-secret   kubernetes.io/dockerconfigjson   1      5d
```

You only need to create the `ngc-api-key` secret:

### Option A: Manual Creation

```bash
# Set your NGC API key
export NGC_API_KEY="your_ngc_api_key_here"

# Create the generic secret
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  --namespace=fraud-detection
```

### Option B: Extract from Existing Secret

If the NGC API key is already in your docker-registry-secret:

```bash
# Extract the password from docker-registry-secret
NGC_KEY=$(oc get secret docker-registry-secret -n fraud-detection \
  -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | \
  jq -r '.auths["nvcr.io"].password')

# Create ngc-api-key secret with extracted value
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_KEY \
  --namespace=fraud-detection
```

### Option C: Use Helper Script

```bash
# Run the helper script
export NGC_API_KEY="your_key"
bash k8s/training-only/create-secrets-openshift.sh
```

## Scenario 2: Fresh OpenShift Deployment

If you don't have any secrets yet:

```bash
export NGC_API_KEY="your_ngc_api_key_here"

# Create docker-registry-secret
oc create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=$NGC_API_KEY \
  --namespace=fraud-detection

# Create ngc-api-key secret
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  --namespace=fraud-detection
```

## Verification

### Check Both Secrets Exist

```bash
oc get secrets -n fraud-detection | grep -E "ngc-api-key|docker-registry-secret"
```

Expected output:
```
docker-registry-secret   kubernetes.io/dockerconfigjson   1      5d
ngc-api-key              Opaque                           1      1m
```

### Verify docker-registry-secret Content

```bash
oc get secret docker-registry-secret -n fraud-detection -o yaml
```

Should show:
```yaml
apiVersion: v1
data:
  .dockerconfigjson: eyJhdXRocyI6eyJuY...  # Base64 encoded
kind: Secret
metadata:
  name: docker-registry-secret
  namespace: fraud-detection
type: kubernetes.io/dockerconfigjson
```

### Verify ngc-api-key Content

```bash
oc get secret ngc-api-key -n fraud-detection -o yaml
```

Should show:
```yaml
apiVersion: v1
data:
  NGC_API_KEY: bnZhcGktWW91ckFQSUtleQ==  # Base64 encoded
kind: Secret
metadata:
  name: ngc-api-key
  namespace: fraud-detection
type: Opaque
```

### Decode and Verify NGC_API_KEY

```bash
# Decode the NGC_API_KEY
oc get secret ngc-api-key -n fraud-detection \
  -o jsonpath='{.data.NGC_API_KEY}' | base64 -d

# Should output your NGC API key
```

## Testing in a Pod

Create a test pod to verify both secrets work:

```bash
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: secret-test
  namespace: fraud-detection
spec:
  imagePullSecrets:
    - name: docker-registry-secret
  containers:
  - name: test
    image: nvcr.io/nvidia/cuda:12.0.0-base-ubuntu22.04
    command: ["sh", "-c", "echo NGC_API_KEY=\$NGC_API_KEY && sleep 3600"]
    env:
    - name: NGC_API_KEY
      valueFrom:
        secretKeyRef:
          name: ngc-api-key
          key: NGC_API_KEY
  restartPolicy: Never
EOF

# Wait for pod to start
oc wait --for=condition=ready pod/secret-test -n fraud-detection --timeout=60s

# Check logs - should show your NGC API key
oc logs secret-test -n fraud-detection

# Clean up
oc delete pod secret-test -n fraud-detection
```

## Common Issues

### Issue 1: ImagePullBackOff

**Error**: `Failed to pull image "nvcr.io/...": unauthorized`

**Cause**: docker-registry-secret is missing or incorrect

**Solution**:
```bash
# Recreate docker-registry-secret
oc delete secret docker-registry-secret -n fraud-detection
oc create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=$NGC_API_KEY \
  --namespace=fraud-detection
```

### Issue 2: Container Fails with "NGC_API_KEY not set"

**Error**: Container logs show NGC_API_KEY is empty

**Cause**: ngc-api-key secret is missing or not referenced correctly

**Solution**:
```bash
# Check if secret exists
oc get secret ngc-api-key -n fraud-detection

# If missing, create it
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  --namespace=fraud-detection

# Verify pod spec references it correctly
oc get deployment fraud-detection-training -n fraud-detection -o yaml | grep -A 5 "env:"
```

### Issue 3: Secret Exists but Wrong Type

**Error**: `error: secret "ngc-api-key" already exists`

**Cause**: Secret exists but is wrong type (e.g., dockerconfigjson instead of Opaque)

**Solution**:
```bash
# Delete and recreate with correct type
oc delete secret ngc-api-key -n fraud-detection
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  --namespace=fraud-detection
```

## Secret Structure Comparison

### docker-registry-secret (dockerconfigjson)

```json
{
  "auths": {
    "nvcr.io": {
      "username": "$oauthtoken",
      "password": "nvapi-YourAPIKey",
      "auth": "JG9hdXRodG9rZW46bnZhcGktWW91ckFQSUtleQ=="
    }
  }
}
```

**Used by**: `imagePullSecrets`

### ngc-api-key (Opaque)

```yaml
data:
  NGC_API_KEY: bnZhcGktWW91ckFQSUtleQ==  # Base64 of "nvapi-YourAPIKey"
```

**Used by**: `env.valueFrom.secretKeyRef`

## Best Practices

1. **Use the same NGC API key** for both secrets
2. **Create secrets before deploying** pods
3. **Store secrets in a secure location** (e.g., OpenShift Secrets Manager, Vault)
4. **Rotate keys regularly** and update both secrets
5. **Use RBAC** to limit access to secrets
6. **Don't commit secrets** to version control

## Automation Script

For automated deployments, use the provided script:

```bash
# Set your NGC API key
export NGC_API_KEY="nvapi-YourAPIKey"

# Run the script
bash k8s/training-only/create-secrets-openshift.sh

# The script will:
# 1. Check if namespace exists
# 2. Check if docker-registry-secret exists
# 3. Extract NGC_API_KEY if possible
# 4. Create ngc-api-key secret
# 5. Verify both secrets
```

## Summary

**Two secrets required**:

| Secret Name | Type | Purpose | Used By |
|-------------|------|---------|---------|
| `docker-registry-secret` | `kubernetes.io/dockerconfigjson` | Pull images from nvcr.io | `imagePullSecrets` |
| `ngc-api-key` | `Opaque` | Provide NGC_API_KEY env var | `env.valueFrom.secretKeyRef` |

**Quick commands**:
```bash
# Create both secrets
export NGC_API_KEY="your_key"

oc create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=$NGC_API_KEY \
  --namespace=fraud-detection

oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  --namespace=fraud-detection

# Verify
oc get secrets -n fraud-detection
```
