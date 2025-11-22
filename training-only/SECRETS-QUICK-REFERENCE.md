# Secrets Quick Reference

## TL;DR

You need **TWO** secrets with the **SAME** NGC API key:

```bash
export NGC_API_KEY="nvapi-YourAPIKey"

# Secret 1: For pulling images
oc create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=$NGC_API_KEY \
  --namespace=fraud-detection

# Secret 2: For environment variable
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  --namespace=fraud-detection
```

## Why Two Secrets?

```
┌─────────────────────────────────────────────────────────────┐
│                         Pod Spec                             │
│                                                              │
│  imagePullSecrets:                                          │
│    - name: docker-registry-secret  ← Secret 1 (pull image)  │
│                                                              │
│  containers:                                                 │
│  - name: training                                            │
│    image: nvcr.io/nvidia/...  ← Pulled using Secret 1       │
│    env:                                                      │
│    - name: NGC_API_KEY                                       │
│      valueFrom:                                              │
│        secretKeyRef:                                         │
│          name: ngc-api-key  ← Secret 2 (env var)            │
│          key: NGC_API_KEY                                    │
└─────────────────────────────────────────────────────────────┘
```

## Secret Types

| Secret | Type | Contains | Purpose |
|--------|------|----------|---------|
| `docker-registry-secret` | `kubernetes.io/dockerconfigjson` | `.dockerconfigjson` | Pull images |
| `ngc-api-key` | `Opaque` | `NGC_API_KEY` | Environment variable |

## If You Already Have docker-registry-secret

```bash
# Just create ngc-api-key
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  --namespace=fraud-detection
```

## Verify

```bash
# Check both exist
oc get secrets -n fraud-detection | grep -E "ngc|docker"

# Should show:
# docker-registry-secret   kubernetes.io/dockerconfigjson   1      5d
# ngc-api-key              Opaque                           1      1m
```

## Test

```bash
# Test image pull
oc run test --image=nvcr.io/nvidia/cuda:12.0.0-base-ubuntu22.04 \
  --overrides='{"spec":{"imagePullSecrets":[{"name":"docker-registry-secret"}]}}' \
  -n fraud-detection

# Test env var
oc run test2 --image=busybox --command -- sh -c 'echo $NGC_API_KEY' \
  --overrides='{"spec":{"containers":[{"name":"test2","image":"busybox","command":["sh","-c","echo $NGC_API_KEY && sleep 60"],"env":[{"name":"NGC_API_KEY","valueFrom":{"secretKeyRef":{"name":"ngc-api-key","key":"NGC_API_KEY"}}}]}]}}' \
  -n fraud-detection

oc logs test2 -n fraud-detection
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ImagePullBackOff` | Missing `docker-registry-secret` | Create docker-registry-secret |
| `NGC_API_KEY not set` | Missing `ngc-api-key` | Create ngc-api-key secret |
| `secret already exists` | Wrong type | Delete and recreate |

## One-Liner Setup

```bash
export NGC_API_KEY="your_key" && \
oc create secret docker-registry docker-registry-secret --docker-server=nvcr.io --docker-username='$oauthtoken' --docker-password=$NGC_API_KEY --namespace=fraud-detection && \
oc create secret generic ngc-api-key --from-literal=NGC_API_KEY=$NGC_API_KEY --namespace=fraud-detection && \
echo "✓ Secrets created successfully"
```

## Automated Script

```bash
bash k8s/training-only/create-secrets-openshift.sh
```
