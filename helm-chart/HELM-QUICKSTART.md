# Helm Chart Quick Start

Deploy fraud detection inference server using Helm on OpenShift.

## Prerequisites

- Helm 3.x installed
- OpenShift cluster access
- NGC API key

## Install Helm (if needed)

```bash
# macOS
brew install helm

# Linux
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Windows
choco install kubernetes-helm

# Verify
helm version
```

## Deploy in 3 Steps

### Step 1: Create NGC Secret

```bash
# Login to OpenShift
oc login --server=https://your-cluster:6443

# Create secret
oc create namespace fraud-detection
oc create secret docker-registry ngc-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password="<YOUR_NGC_API_KEY>" \
  --namespace=fraud-detection
```

### Step 2: Install Helm Chart

```bash
# Navigate to helm chart directory
cd k8s/helm-chart/

# Install with default values
helm install fraud-detection ./fraud-detection-inference

# Or install with custom values
helm install fraud-detection ./fraud-detection-inference \
  --set replicaCount=2 \
  --set persistence.size=10Gi
```

### Step 3: Upload Models

```bash
# Wait for PVC to be ready
kubectl wait --for=condition=Bound pvc/fraud-detection-fraud-detection-inference-models -n fraud-detection

# Create upload pod
kubectl run model-uploader --image=busybox --restart=Never -n fraud-detection \
  --overrides='{
    "spec": {
      "containers": [{
        "name": "uploader",
        "image": "busybox",
        "command": ["sleep", "3600"],
        "volumeMounts": [{
          "name": "models",
          "mountPath": "/models"
        }]
      }],
      "volumes": [{
        "name": "models",
        "persistentVolumeClaim": {
          "claimName": "fraud-detection-fraud-detection-inference-models"
        }
      }]
    }
  }'

# Wait for pod
kubectl wait --for=condition=Ready pod/model-uploader -n fraud-detection

# Upload models (replace with your local path)
kubectl cp ./model_output_dir/python_backend_model_repository \
  fraud-detection/model-uploader:/models/

# Cleanup
kubectl delete pod model-uploader -n fraud-detection
```

## Verify Deployment

```bash
# Check Helm release
helm status fraud-detection

# Check pods
kubectl get pods -n fraud-detection

# Get inference URL
export INFERENCE_URL=$(oc get route fraud-detection-fraud-detection-inference -n fraud-detection -o jsonpath='{.spec.host}')
echo "Inference URL: https://${INFERENCE_URL}"

# Test health
curl -k https://${INFERENCE_URL}/v2/health/ready
```

## Common Commands

### View Configuration

```bash
# Get current values
helm get values fraud-detection

# Get all values (including defaults)
helm get values fraud-detection --all

# View manifest
helm get manifest fraud-detection
```

### Update Deployment

```bash
# Scale replicas
helm upgrade fraud-detection ./fraud-detection-inference \
  --set replicaCount=3 \
  --reuse-values

# Update image version
helm upgrade fraud-detection ./fraud-detection-inference \
  --set image.tag=25.05-py3 \
  --reuse-values

# Enable autoscaling
helm upgrade fraud-detection ./fraud-detection-inference \
  --set autoscaling.enabled=true \
  --set autoscaling.minReplicas=2 \
  --set autoscaling.maxReplicas=5 \
  --reuse-values
```

### Rollback

```bash
# View history
helm history fraud-detection

# Rollback to previous version
helm rollback fraud-detection

# Rollback to specific revision
helm rollback fraud-detection 2
```

### Uninstall

```bash
# Uninstall release (keeps PVC)
helm uninstall fraud-detection

# Delete PVC manually if needed
kubectl delete pvc fraud-detection-fraud-detection-inference-models -n fraud-detection

# Delete namespace
kubectl delete namespace fraud-detection
```

## Environment-Specific Deployments

### Development

```bash
# Create dev values file
cat > dev-values.yaml <<EOF
replicaCount: 1
resources:
  requests:
    cpu: "1"
    memory: "4Gi"
  limits:
    cpu: "2"
    memory: "8Gi"
persistence:
  size: 2Gi
EOF

# Install
helm install fraud-detection-dev ./fraud-detection-inference \
  -f dev-values.yaml \
  --namespace fraud-detection-dev \
  --create-namespace
```

### Production

```bash
# Create prod values file
cat > prod-values.yaml <<EOF
replicaCount: 3
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
resources:
  requests:
    cpu: "4"
    memory: "16Gi"
  limits:
    cpu: "8"
    memory: "32Gi"
persistence:
  size: 20Gi
route:
  host: fraud-detection.prod.example.com
EOF

# Install
helm install fraud-detection-prod ./fraud-detection-inference \
  -f prod-values.yaml \
  --namespace fraud-detection-prod \
  --create-namespace
```

## Monitoring

```bash
# Watch pods
kubectl get pods -n fraud-detection -w

# View logs
kubectl logs -f -l app.kubernetes.io/name=fraud-detection-inference -n fraud-detection

# Check resource usage
kubectl top pods -n fraud-detection

# Check GPU usage
kubectl exec -it <pod-name> -n fraud-detection -- nvidia-smi
```

## Troubleshooting

### Helm Issues

```bash
# Debug installation
helm install fraud-detection ./fraud-detection-inference --dry-run --debug

# Validate chart
helm lint ./fraud-detection-inference

# Template chart
helm template fraud-detection ./fraud-detection-inference
```

### Pod Issues

```bash
# Describe pod
kubectl describe pod <pod-name> -n fraud-detection

# Check events
kubectl get events -n fraud-detection --sort-by='.lastTimestamp'

# Check logs
kubectl logs <pod-name> -n fraud-detection --previous
```

## Using Helm from OpenShift Console

1. **Install Helm CLI** on your local machine
2. **Login** to OpenShift: `oc login`
3. **Run Helm commands** from terminal
4. **View resources** in OpenShift Console

OpenShift Console shows Helm releases in the "Helm" section of the Developer perspective.

## Next Steps

- See [fraud-detection-inference/README.md](fraud-detection-inference/README.md) for full documentation
- Customize [values.yaml](fraud-detection-inference/values.yaml) for your environment
- Set up monitoring and alerting
- Configure autoscaling based on load

## Benefits of Helm

✅ **Templating**: Reusable configurations
✅ **Versioning**: Track deployment history
✅ **Rollback**: Easy rollback to previous versions
✅ **Packaging**: Bundle all resources together
✅ **Values**: Environment-specific configurations
✅ **Upgrades**: Seamless updates

Happy deploying! 🚀
