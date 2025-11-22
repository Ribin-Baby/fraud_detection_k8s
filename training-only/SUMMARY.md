# Training Deployment Summary

## Overview

This directory contains Kubernetes/OpenShift manifests for deploying the fraud detection model training job. It uses the **same namespace** (`fraud-detection`) as the inference deployment for unified management.

## Key Changes for OpenShift

### 1. Namespace
- **Changed from:** `fraud-detection-training`
- **Changed to:** `fraud-detection` (shared with inference)

### 2. Security Context
Added OpenShift-compatible security contexts:
```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
```

### 3. Routes
Added OpenShift Route for external access:
```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: fraud-detection-training-route
spec:
  tls:
    termination: edge
```

### 4. Node Selector
Updated for OpenShift GPU nodes:
```yaml
nodeSelector:
  nvidia.com/gpu.present: "true"
```

### 5. Storage Class
Added comments for OpenShift storage classes:
```yaml
# storageClassName: ocs-storagecluster-ceph-rbd  # OpenShift Container Storage
# storageClassName: gp2  # AWS EBS
```

## Files

| File | Purpose | OpenShift-Specific |
|------|---------|-------------------|
| `namespace.yaml` | Creates `fraud-detection` namespace | ✓ Labels updated |
| `pvc.yaml` | PVCs for data and models | ✓ Storage class comments |
| `configmap.yaml` | Training configuration | - |
| `secret.yaml` | NGC credentials | ✓ Link to SA instructions |
| `deployment.yaml` | Long-running training server | ✓ Security context, labels |
| `service.yaml` | Service + Route | ✓ Route added |
| `job.yaml` | One-time training job | ✓ Security context |
| `deploy.sh` | Automated deployment | ✓ Detects oc/kubectl |
| `README.md` | Full documentation | ✓ Updated |
| `QUICK-START.md` | Quick start guide | ✓ Updated |
| `OPENSHIFT-DEPLOYMENT.md` | OpenShift-specific guide | ✓ New file |

## Deployment Comparison

### Docker Command
```bash
docker run -d -it --rm \
  --name=financial-fraud-training \
  --gpus "device=0" \
  -p 8002:8002 \
  -p 50051:50051 \
  -e NIM_HTTP_API_PORT=8002 \
  -e NIM_GRPC_API_PORT=50051 \
  -e NIM_DISABLE_MODEL_DOWNLOAD=True \
  -e NGC_API_KEY=$NGC_API_KEY \
  -v /path/to/data:/data \
  -v /path/to/models:/trained_models \
  nvcr.io/nvidia/cugraph/financial-fraud-training:1.0.1

curl -X POST "http://localhost:8002/train" \
  -H "Content-Type: application/json" \
  -d @training_config.json
```

### Kubernetes/OpenShift
```bash
# Deploy
bash deploy.sh

# Or manually
oc apply -f namespace.yaml
oc apply -f pvc.yaml
oc apply -f configmap.yaml
oc create secret generic ngc-api-key --from-literal=NGC_API_KEY=$NGC_API_KEY -n fraud-detection
oc create secret docker-registry docker-registry-secret --docker-server=nvcr.io --docker-username='$oauthtoken' --docker-password=$NGC_API_KEY -n fraud-detection
oc apply -f job.yaml

# Monitor
oc logs -f job/fraud-detection-training-job -n fraud-detection
```

## Quick Start

### For Kubernetes
```bash
export NGC_API_KEY="your_key"
cd k8s/training-only
bash deploy.sh
```

### For OpenShift
```bash
oc login
export NGC_API_KEY="your_key"
cd k8s/training-only
bash deploy.sh
```

The script automatically detects if you're using OpenShift (`oc`) or Kubernetes (`kubectl`).

## Resource Requirements

| Resource | Request | Limit |
|----------|---------|-------|
| GPU | 1 | 1 |
| Memory | 16Gi | 32Gi |
| CPU | 4 cores | 8 cores |
| Data Storage | 50Gi | - |
| Model Storage | 20Gi | - |

## Output

Training produces:
```
/trained_models/python_backend_model_repository/
└── prediction_and_shapley/
    ├── 1/
    │   ├── model.py
    │   ├── state_dict_gnn_model.pth
    │   └── embedding_based_xgboost.json
    └── config.pbtxt
```

## Integration with Inference

Both training and inference use the same namespace (`fraud-detection`), making it easy to:

1. **Share PVCs** - Models trained can be directly used by inference
2. **Unified monitoring** - View all resources in one namespace
3. **Simplified RBAC** - Single set of permissions
4. **Easier management** - One namespace to manage

### Workflow

```
1. Training (this directory)
   ↓
   Produces models in fraud-detection-models-pvc
   ↓
2. Inference (../inference-only/)
   ↓
   Mounts same fraud-detection-models-pvc
   ↓
3. Serve predictions
```

## Documentation

- **README.md** - Comprehensive guide for Kubernetes
- **OPENSHIFT-DEPLOYMENT.md** - OpenShift-specific instructions
- **QUICK-START.md** - 5-minute quick start
- **SUMMARY.md** - This file

## Next Steps

After training:
1. Verify models: `oc exec -n fraud-detection <pod> -- ls /trained_models`
2. Deploy inference: `cd ../inference-only && bash deploy.sh`
3. Test predictions: See inference documentation

## Support

For issues:
- Check logs: `oc logs -f job/fraud-detection-training-job -n fraud-detection`
- Check events: `oc get events -n fraud-detection --sort-by='.lastTimestamp'`
- Check GPU: `oc describe node <gpu-node> | grep nvidia.com/gpu`
