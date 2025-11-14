# Fraud Detection Inference Helm Chart

A Helm chart for deploying NVIDIA Triton Inference Server for fraud detection on OpenShift.

## Prerequisites

- OpenShift 4.12+ cluster
- Helm 3.x installed
- NVIDIA GPU Operator installed on cluster
- NGC API key from NVIDIA
- Trained models ready to upload

## Quick Start

```bash
# 1. Add NGC secret
oc create secret docker-registry ngc-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password="<NGC_API_KEY>" \
  --namespace=fraud-detection

# 2. Install chart
helm install fraud-detection ./fraud-detection-inference

# 3. Upload models
kubectl run model-uploader --image=busybox --restart=Never \
  --overrides='{"spec":{"containers":[{"name":"uploader","image":"busybox","command":["sleep","3600"],"volumeMounts":[{"name":"models","mountPath":"/models"}]}],"volumes":[{"name":"models","persistentVolumeClaim":{"claimName":"fraud-detection-fraud-detection-inference-models"}}]}}'

kubectl cp ./model_output_dir/python_backend_model_repository \
  model-uploader:/models/

kubectl delete pod model-uploader

# 4. Get inference URL
export INFERENCE_URL=$(oc get route fraud-detection-fraud-detection-inference -o jsonpath='{.spec.host}')
curl -k https://${INFERENCE_URL}/v2/health/ready
```

## Configuration

### Basic Configuration

```yaml
# values.yaml
replicaCount: 1

resources:
  requests:
    cpu: "2"
    memory: "8Gi"
    nvidia.com/gpu: "1"
  limits:
    cpu: "4"
    memory: "16Gi"
    nvidia.com/gpu: "1"

persistence:
  size: 5Gi
```

### Custom Values

```bash
# Install with custom values
helm install fraud-detection ./fraud-detection-inference \
  --set replicaCount=3 \
  --set persistence.size=10Gi \
  --set resources.requests.memory=16Gi
```

### Values File

```bash
# Create custom values file
cat > my-values.yaml <<EOF
replicaCount: 3

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5
  targetCPUUtilizationPercentage: 70

persistence:
  size: 10Gi
  storageClass: fast-ssd

resources:
  requests:
    cpu: "4"
    memory: "16Gi"
    nvidia.com/gpu: "1"
  limits:
    cpu: "8"
    memory: "32Gi"
    nvidia.com/gpu: "1"
EOF

# Install with custom values
helm install fraud-detection ./fraud-detection-inference -f my-values.yaml
```

## Parameters

### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `namespace.create` | Create namespace | `true` |
| `namespace.name` | Namespace name | `fraud-detection` |

### Image Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Triton image repository | `nvcr.io/nvidia/tritonserver` |
| `image.tag` | Image tag | `25.04-py3` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `imagePullSecrets` | Image pull secrets | `[{name: ngc-secret}]` |

### Deployment Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `nodeSelector` | Node selector for GPU nodes | `{nvidia.com/gpu.present: "true"}` |

### Resource Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `resources.requests.cpu` | CPU request | `2` |
| `resources.requests.memory` | Memory request | `8Gi` |
| `resources.requests.nvidia.com/gpu` | GPU request | `1` |
| `resources.limits.cpu` | CPU limit | `4` |
| `resources.limits.memory` | Memory limit | `16Gi` |
| `resources.limits.nvidia.com/gpu` | GPU limit | `1` |

### Autoscaling Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `autoscaling.enabled` | Enable HPA | `false` |
| `autoscaling.minReplicas` | Minimum replicas | `1` |
| `autoscaling.maxReplicas` | Maximum replicas | `5` |
| `autoscaling.targetCPUUtilizationPercentage` | Target CPU % | `70` |

### Persistence Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `persistence.enabled` | Enable PVC | `true` |
| `persistence.storageClass` | Storage class | `""` (default) |
| `persistence.accessMode` | Access mode | `ReadWriteOnce` |
| `persistence.size` | Storage size | `5Gi` |
| `persistence.existingClaim` | Use existing PVC | `""` |

### Service Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.type` | Service type | `ClusterIP` |
| `service.httpPort` | HTTP port | `8005` |
| `service.grpcPort` | gRPC port | `8006` |
| `service.metricsPort` | Metrics port | `8007` |

### Route Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `route.enabled` | Enable OpenShift Route | `true` |
| `route.host` | Custom hostname | `""` (auto-generated) |
| `route.tls.enabled` | Enable TLS | `true` |
| `route.tls.termination` | TLS termination | `edge` |

### Triton Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `triton.modelRepository` | Model repository path | `/models/python_backend_model_repository` |
| `triton.httpPort` | HTTP port | `8005` |
| `triton.grpcPort` | gRPC port | `8006` |
| `triton.metricsPort` | Metrics port | `8007` |
| `triton.exitTimeoutSecs` | Exit timeout | `6000` |

## Common Operations

### Upgrade

```bash
# Upgrade with new values
helm upgrade fraud-detection ./fraud-detection-inference \
  --set replicaCount=3

# Upgrade with new image version
helm upgrade fraud-detection ./fraud-detection-inference \
  --set image.tag=25.05-py3
```

### Rollback

```bash
# List releases
helm history fraud-detection

# Rollback to previous version
helm rollback fraud-detection

# Rollback to specific revision
helm rollback fraud-detection 2
```

### Uninstall

```bash
# Uninstall release
helm uninstall fraud-detection

# Uninstall and delete namespace
helm uninstall fraud-detection
oc delete namespace fraud-detection
```

### Status

```bash
# Check release status
helm status fraud-detection

# List all releases
helm list

# Get values
helm get values fraud-detection
```

## Examples

### Development Environment

```yaml
# dev-values.yaml
replicaCount: 1

resources:
  requests:
    cpu: "1"
    memory: "4Gi"
    nvidia.com/gpu: "1"
  limits:
    cpu: "2"
    memory: "8Gi"
    nvidia.com/gpu: "1"

persistence:
  size: 2Gi
```

```bash
helm install fraud-detection ./fraud-detection-inference -f dev-values.yaml
```

### Production Environment

```yaml
# prod-values.yaml
replicaCount: 3

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 60

resources:
  requests:
    cpu: "4"
    memory: "16Gi"
    nvidia.com/gpu: "1"
  limits:
    cpu: "8"
    memory: "32Gi"
    nvidia.com/gpu: "1"

persistence:
  size: 20Gi
  storageClass: fast-ssd

route:
  host: fraud-detection.production.example.com
```

```bash
helm install fraud-detection ./fraud-detection-inference -f prod-values.yaml
```

## Troubleshooting

### Check Helm Release

```bash
helm status fraud-detection
helm get manifest fraud-detection
helm get values fraud-detection
```

### Check Resources

```bash
kubectl get all -n fraud-detection
kubectl describe deployment fraud-detection-fraud-detection-inference -n fraud-detection
kubectl logs -l app.kubernetes.io/name=fraud-detection-inference -n fraud-detection
```

### Common Issues

**PVC Not Binding**
```bash
kubectl get pvc -n fraud-detection
kubectl describe pvc fraud-detection-fraud-detection-inference-models -n fraud-detection
```

**Pod Not Starting**
```bash
kubectl describe pod -l app.kubernetes.io/name=fraud-detection-inference -n fraud-detection
kubectl logs -l app.kubernetes.io/name=fraud-detection-inference -n fraud-detection
```

**GPU Not Available**
```bash
kubectl describe nodes -l nvidia.com/gpu.present=true
```

## License

See [LICENSE](../../../LICENSE) file.
