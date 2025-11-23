# Inference-Only Deployment Summary

## 🎯 Simplified Approach

This deployment focuses **only on the inference server**, keeping your existing local Docker workflow for data preprocessing and model training.

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR WORKFLOW                             │
└─────────────────────────────────────────────────────────────┘

LOCAL (Docker)                    OPENSHIFT (Kubernetes)
┌──────────────────┐             ┌─────────────────────────┐
│                  │             │                         │
│ 1. Preprocess    │             │  Triton Inference       │
│    Data          │             │  Server                 │
│    (Notebook)    │             │                         │
│        ↓         │             │  - GPU Support          │
│ 2. Train Model   │   Upload    │  - Auto-scaling         │
│    (Docker)      │─────────────→  - Health Checks        │
│        ↓         │   Models    │  - HTTPS Route          │
│ 3. Trained       │             │                         │
│    Models        │             │  External API           │
│                  │             │  (Predictions)          │
└──────────────────┘             └─────────────────────────┘
```

## ✨ Key Benefits

| Aspect | Benefit |
|--------|---------|
| **Simplicity** | Keep existing local training workflow |
| **Cost** | Only pay for GPU during inference (not training) |
| **Flexibility** | Train locally, deploy inference anywhere |
| **Scalability** | Scale inference replicas independently |
| **Speed** | Fast iteration - train local, deploy quick |

## 📁 What You Deploy

Only these components go to OpenShift:

1. **PVC** (5Gi) - Storage for trained models
2. **Deployment** - Triton Inference Server with GPU
3. **Service** - Internal networking (HTTP, gRPC, metrics)
4. **Route** - External HTTPS access

## 🚀 Quick Deploy

```bash
# 1. Train locally (existing workflow)
# Run your Jupyter notebook with Docker

# 2. Deploy to OpenShift
export NGC_API_KEY="your-key"
oc create namespace fraud-detection
oc create secret docker-registry ngc-secret \
  --docker-server=nvcr.io --docker-username='$oauthtoken' \
  --docker-password="${NGC_API_KEY}" -n fraud-detection

# 3. Upload models and deploy
cd k8s/inference-only/
oc apply -k .
oc apply -f upload-pod.yaml
oc cp ./model_output_dir/python_backend_model_repository \
  fraud-detection/model-uploader:/models/
oc delete pod model-uploader -n fraud-detection

# 4. Done!
INFERENCE_URL=$(oc get route fraud-detection-inference -n fraud-detection -o jsonpath='{.spec.host}')
curl -k https://${INFERENCE_URL}/v2/health/ready
```

## 📂 Directory Structure

```
k8s/inference-only/
├── README.md                      # Overview
├── QUICK-START.md                 # 5-minute deploy guide
├── DEPLOYMENT.md                  # Detailed instructions
├── namespace.yaml                 # Namespace
├── pvc.yaml                       # Model storage
├── upload-pod.yaml                # Upload helper
├── inference-deployment.yaml      # Triton server
├── inference-service.yaml         # Service
├── inference-route.yaml           # External access
└── kustomization.yaml             # Deploy all
```

## 🔄 Typical Workflow

### Initial Deployment
```bash
1. Train model locally (Docker)
2. Upload models to OpenShift PVC
3. Deploy inference server
4. Test inference endpoint
```

### Model Updates
```bash
1. Retrain model locally (Docker)
2. Upload new models to PVC
3. Restart inference deployment
4. New models automatically loaded
```

## 🎛️ Configuration

### Resource Allocation
```yaml
CPU: 2-4 cores
Memory: 8-16Gi
GPU: 1x NVIDIA GPU per replica
Storage: 5Gi PVC
```

### Scaling
```bash
# Manual scaling
oc scale deployment fraud-detection-inference --replicas=3

# Auto-scaling
oc autoscale deployment fraud-detection-inference \
  --min=1 --max=5 --cpu-percent=70
```

## 🔍 Monitoring

```bash
# Health checks
curl https://${INFERENCE_URL}/v2/health/live
curl https://${INFERENCE_URL}/v2/health/ready

# Metrics
curl https://${INFERENCE_URL}:8007/metrics

# Logs
oc logs -f deployment/fraud-detection-inference -n fraud-detection

# GPU usage
oc exec <pod-name> -n fraud-detection -- nvidia-smi
```

## 🐍 Python Client Example

```python
import requests
import numpy as np

# OpenShift inference endpoint
INFERENCE_URL = "https://fraud-detection-inference-fraud-detection.apps.your-cluster.com"

# Prepare your data (same as local workflow)
payload = {
    "inputs": [
        {
            "name": "NODE_FEATURES",
            "shape": [batch_size, num_features],
            "datatype": "FP32",
            "data": features.flatten().tolist()
        },
        {
            "name": "EDGE_INDEX",
            "shape": [2, num_edges],
            "datatype": "INT64",
            "data": edges.flatten().tolist()
        },
        {
            "name": "COMPUTE_SHAP",
            "shape": [1],
            "datatype": "BOOL",
            "data": [False]
        },
        {
            "name": "FEATURE_MASK",
            "shape": [num_features],
            "datatype": "INT32",
            "data": [0] * num_features
        }
    ]
}

# Call inference
response = requests.post(
    f"{INFERENCE_URL}/v2/models/prediction_and_shapley/infer",
    json=payload,
    verify=False  # Use True with proper certs in production
)

# Get predictions
predictions = response.json()["outputs"][0]["data"]
print(f"Fraud scores: {predictions}")
```

## 🛠️ OpenShift Dashboard Deployment

You can also deploy via the OpenShift web console:

1. Login to OpenShift Console
2. Create Project: `fraud-detection`
3. Click "+Add" → "Import YAML"
4. Paste each YAML file and create
5. Use Terminal to upload models
6. Monitor in Topology view

## 🔄 Comparison with Full Deployment

| Aspect | Inference-Only | Full Deployment |
|--------|---------------|-----------------|
| **Complexity** | Simple | Complex |
| **Components** | 4 resources | 10+ resources |
| **Training** | Local Docker | OpenShift Jobs |
| **Preprocessing** | Local Docker | OpenShift Jobs |
| **Inference** | OpenShift | OpenShift |
| **Cost** | Lower | Higher |
| **Flexibility** | High | Medium |
| **Best For** | Development, Iteration | Production, Automation |

## 📚 Documentation

- **[QUICK-START.md](inference-only/QUICK-START.md)** - 5-minute deployment
- **[DEPLOYMENT.md](inference-only/DEPLOYMENT.md)** - Detailed guide
- **[README.md](inference-only/README.md)** - Overview

## ✅ When to Use This Approach

**Use Inference-Only When:**
- ✅ You have an existing local training workflow
- ✅ Training happens infrequently
- ✅ You want to iterate quickly
- ✅ You need flexible training environment
- ✅ Cost optimization is important

**Use Full Deployment When:**
- ✅ Training needs to be automated
- ✅ Training happens frequently
- ✅ You need end-to-end pipeline
- ✅ Multiple teams need access
- ✅ Compliance requires cloud training

## 🎓 Summary

The inference-only deployment:
1. **Keeps** your existing local Docker training workflow
2. **Deploys** only the inference server to OpenShift
3. **Provides** scalable, production-ready inference API
4. **Simplifies** operations and reduces costs
5. **Enables** fast iteration and updates

Perfect for teams that want to leverage Kubernetes for inference while maintaining flexibility in their training workflow!

---

**Ready to deploy?** Start with [QUICK-START.md](inference-only/QUICK-START.md)!
