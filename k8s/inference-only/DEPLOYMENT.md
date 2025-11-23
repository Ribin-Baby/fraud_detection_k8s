# Inference-Only Deployment Guide

This guide shows how to deploy **only the Triton Inference Server** to OpenShift, keeping data preprocessing and model training as local Docker workflows.

## Prerequisites

### Local Environment
- Docker installed
- Trained models from local workflow at: `model_output_dir/python_backend_model_repository/`

### OpenShift Cluster
- OpenShift 4.12+ with GPU nodes
- NVIDIA GPU Operator installed
- `oc` CLI tool configured
- NGC API key from NVIDIA

## Step-by-Step Deployment

### Step 1: Train Model Locally (Existing Workflow)

Run your existing Docker-based workflow from the notebook:

```python
# In your Jupyter notebook (financial-fraud-usage.ipynb)

# 1. Preprocess data
from preprocess_TabFormer import preprocess_data
mask_mapping, feature_mask = preprocess_data(data_root_dir)

# 2. Train model using Docker
!docker run --gpus "device=0" -d \
    -v {gnn_data_dir}:/data \
    -v {model_output_dir}:/trained_models \
    nvcr.io/nvidia/cugraph/financial-fraud-training:1.0.1

# 3. Verify model output
# You should have: model_output_dir/python_backend_model_repository/
```

### Step 2: Prepare OpenShift Environment

```bash
# Set your NGC API key
export NGC_API_KEY="your-ngc-api-key-here"

# Login to OpenShift
oc login --server=https://your-openshift-cluster:6443

# Create namespace
oc apply -f namespace.yaml

# Create NGC registry secret
oc create secret docker-registry ngc-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password="${NGC_API_KEY}" \
  --namespace=fraud-detection

# Verify secret
oc get secret ngc-secret -n fraud-detection
```

### Step 3: Create Storage for Models

```bash
# Create PVC for models
oc apply -f pvc.yaml

# Wait for PVC to bind
oc get pvc fraud-detection-models -n fraud-detection -w

# Expected output: STATUS = Bound
```

### Step 4: Upload Trained Models

```bash
# Create temporary upload pod
oc apply -f upload-pod.yaml

# Wait for pod to be ready
oc wait --for=condition=Ready pod/model-uploader -n fraud-detection --timeout=60s

# Upload your trained models
# Replace ./model_output_dir with your actual local path
oc cp ./model_output_dir/python_backend_model_repository \
  fraud-detection/model-uploader:/models/

# Verify upload
oc exec model-uploader -n fraud-detection -- ls -R /models/

# Expected structure:
# /models/python_backend_model_repository/
# └── prediction_and_shapley/
#     ├── 1/
#     │   ├── embedding_based_xgboost.json
#     │   ├── model.py
#     │   └── state_dict_gnn_model.pth
#     └── config.pbtxt

# Delete upload pod
oc delete pod model-uploader -n fraud-detection
```

### Step 5: Deploy Inference Server

```bash
# Deploy all inference resources
oc apply -f inference-deployment.yaml
oc apply -f inference-service.yaml
oc apply -f inference-route.yaml

# Or use kustomize
oc apply -k .

# Wait for deployment to be ready
oc wait --for=condition=Available deployment/fraud-detection-inference \
  -n fraud-detection --timeout=300s

# Check pod status
oc get pods -l component=inference -n fraud-detection

# View logs
oc logs -f deployment/fraud-detection-inference -n fraud-detection
```

### Step 6: Verify Deployment

```bash
# Get the inference URL
INFERENCE_URL=$(oc get route fraud-detection-inference \
  -n fraud-detection -o jsonpath='{.spec.host}')

echo "Inference URL: https://${INFERENCE_URL}"

# Test health endpoints
curl -k https://${INFERENCE_URL}/v2/health/live
# Expected: {"live":true}

curl -k https://${INFERENCE_URL}/v2/health/ready
# Expected: {"ready":true}

# List available models
curl -k https://${INFERENCE_URL}/v2/models
# Expected: prediction_and_shapley model listed

# Get model metadata
curl -k https://${INFERENCE_URL}/v2/models/prediction_and_shapley
```

### Step 7: Test Inference

Use the same inference code from your notebook, just change the URL:

```python
import requests
import numpy as np

# Use OpenShift route instead of localhost
INFERENCE_URL = "https://fraud-detection-inference-fraud-detection.apps.your-cluster.com"

# Your existing inference code
payload = {
    "inputs": [
        {
            "name": "NODE_FEATURES",
            "shape": list(test_features.shape),
            "datatype": "FP32",
            "data": test_features.flatten().tolist()
        },
        {
            "name": "EDGE_INDEX",
            "shape": list(test_edges.shape),
            "datatype": "INT64",
            "data": test_edges.flatten().tolist()
        },
        {
            "name": "COMPUTE_SHAP",
            "shape": [1],
            "datatype": "BOOL",
            "data": [False]
        },
        {
            "name": "FEATURE_MASK",
            "shape": [50],
            "datatype": "INT32",
            "data": [0] * 50
        }
    ]
}

response = requests.post(
    f"{INFERENCE_URL}/v2/models/prediction_and_shapley/infer",
    json=payload,
    verify=False  # Use verify=True in production with proper certs
)

predictions = response.json()["outputs"][0]["data"]
print(f"Predictions: {predictions}")
```

## Updating Models (Retraining)

When you retrain your model locally:

```bash
# 1. Train new model locally (Docker workflow)

# 2. Create upload pod
oc apply -f upload-pod.yaml
oc wait --for=condition=Ready pod/model-uploader -n fraud-detection

# 3. Upload new models (overwrites old ones)
oc exec model-uploader -n fraud-detection -- rm -rf /models/python_backend_model_repository
oc cp ./model_output_dir/python_backend_model_repository \
  fraud-detection/model-uploader:/models/

# 4. Delete upload pod
oc delete pod model-uploader -n fraud-detection

# 5. Restart inference to load new models
oc rollout restart deployment/fraud-detection-inference -n fraud-detection

# 6. Wait for rollout
oc rollout status deployment/fraud-detection-inference -n fraud-detection

# 7. Verify new models loaded
curl -k https://${INFERENCE_URL}/v2/health/ready
```

## Scaling

```bash
# Scale up for higher load
oc scale deployment fraud-detection-inference --replicas=3 -n fraud-detection

# Scale down
oc scale deployment fraud-detection-inference --replicas=1 -n fraud-detection

# Auto-scaling based on CPU
oc autoscale deployment fraud-detection-inference \
  --min=1 --max=5 --cpu-percent=70 -n fraud-detection
```

## Monitoring

```bash
# Check pod status
oc get pods -l component=inference -n fraud-detection

# View logs
oc logs -f deployment/fraud-detection-inference -n fraud-detection

# Check resource usage
oc adm top pods -n fraud-detection

# Check GPU usage
oc exec <pod-name> -n fraud-detection -- nvidia-smi

# Access metrics
curl -k https://${INFERENCE_URL}:8007/metrics
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod events
oc describe pod <pod-name> -n fraud-detection

# Common issues:
# - GPU not available: Check GPU Operator
# - Image pull error: Verify NGC secret
# - PVC not bound: Check storage class
```

### Models Not Loading

```bash
# Check if models exist in PVC
oc run model-checker --image=busybox --rm -it --restart=Never \
  --overrides='{
    "spec": {
      "containers": [{
        "name": "checker",
        "image": "busybox",
        "command": ["ls", "-R", "/models"],
        "volumeMounts": [{
          "name": "models",
          "mountPath": "/models"
        }]
      }],
      "volumes": [{
        "name": "models",
        "persistentVolumeClaim": {
          "claimName": "fraud-detection-models"
        }
      }]
    }
  }' -n fraud-detection

# Check Triton logs
oc logs -l component=inference -n fraud-detection | grep -i error
```

### Health Checks Failing

```bash
# Check readiness probe
oc describe pod <pod-name> -n fraud-detection | grep -A 10 Readiness

# Increase initial delay if models take long to load
oc edit deployment fraud-detection-inference -n fraud-detection
# Modify: initialDelaySeconds: 120
```

## Using OpenShift Dashboard

You can also deploy using the OpenShift web console:

1. **Login** to OpenShift Console
2. **Create Project**: `fraud-detection`
3. **Import YAML**: Click "+Add" → "Import YAML"
4. **Paste** contents of each YAML file
5. **Create** resources one by one:
   - namespace.yaml
   - pvc.yaml
   - inference-deployment.yaml
   - inference-service.yaml
   - inference-route.yaml
6. **Upload Models**: Use terminal in console to run upload commands
7. **Monitor**: Use Topology view to see deployment status

## Cleanup

```bash
# Delete all resources
oc delete -k .

# Or delete namespace (removes everything)
oc delete namespace fraud-detection
```

## Summary

This deployment approach:
- ✅ Keeps your existing local training workflow
- ✅ Only deploys inference to OpenShift
- ✅ Provides scalable, production-ready inference
- ✅ Supports easy model updates
- ✅ Includes monitoring and health checks
- ✅ Exposes HTTPS endpoint for external access

Your workflow becomes:
1. **Local**: Train model with Docker (existing notebook)
2. **Upload**: Copy models to OpenShift PVC
3. **Deploy**: Inference server automatically loads and serves models
4. **Use**: Call inference API from anywhere

Simple, flexible, and production-ready! 🚀
