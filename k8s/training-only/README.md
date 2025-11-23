# Fraud Detection Training on Kubernetes/OpenShift

This directory contains Kubernetes/OpenShift manifests for running the fraud detection model training job.

**Note:** This uses the same `fraud-detection` namespace as the inference deployment for easier management.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Namespace: fraud-detection                        │    │
│  │                                                     │    │
│  │  ┌──────────────────────────────────────────┐     │    │
│  │  │  Training Pod (GPU)                      │     │    │
│  │  │  ┌────────────────────────────────────┐  │     │    │
│  │  │  │  Container:                        │  │     │    │
│  │  │  │  financial-fraud-training:1.0.1    │  │     │    │
│  │  │  │                                    │  │     │    │
│  │  │  │  Ports: 8002 (HTTP), 50051 (gRPC) │  │     │    │
│  │  │  └────────────────────────────────────┘  │     │    │
│  │  │                                           │     │    │
│  │  │  Volumes:                                 │     │    │
│  │  │  - /data (PVC: fraud-detection-data-pvc) │     │    │
│  │  │  - /trained_models (PVC: models-pvc)     │     │    │
│  │  │  - /config (ConfigMap: training-config)  │     │    │
│  │  └──────────────────────────────────────────┘     │    │
│  │                                                     │    │
│  │  ┌──────────────────────────────────────────┐     │    │
│  │  │  Service: training-service               │     │    │
│  │  │  - ClusterIP: 8002, 50051                │     │    │
│  │  │  - NodePort: 30002, 30051 (optional)     │     │    │
│  │  └──────────────────────────────────────────┘     │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Kubernetes cluster** with GPU support
2. **NVIDIA GPU Operator** installed
3. **NGC API Key** from NVIDIA
4. **Storage class** for PersistentVolumes
5. **Preprocessed data** in the data PVC

## Files Overview

```
k8s/training-only/
├── namespace.yaml       # Creates fraud-detection-training namespace
├── pvc.yaml            # PersistentVolumeClaims for data and models
├── configmap.yaml      # Training configuration
├── secret.yaml         # NGC API key and registry credentials
├── deployment.yaml     # Long-running training server (optional)
├── service.yaml        # Service to expose training API
├── job.yaml            # One-time training job (recommended)
├── README.md           # This file
└── deploy.sh           # Helper script to deploy everything
```

## Deployment Options

### Option 1: Training Job (Recommended)

Use this for one-time training runs:

```bash
# Deploy everything
kubectl apply -f namespace.yaml
kubectl apply -f pvc.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml  # Edit with your NGC API key first!
kubectl apply -f job.yaml

# Monitor job
kubectl get jobs -n fraud-detection-training
kubectl logs -f job/fraud-detection-training-job -n fraud-detection-training
```

### Option 2: Training Server (For Multiple Runs)

Use this if you want to trigger multiple training runs:

```bash
# Deploy server
kubectl apply -f namespace.yaml
kubectl apply -f pvc.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml  # Edit with your NGC API key first!
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=fraud-detection-training -n fraud-detection-training --timeout=300s

# Trigger training via API
kubectl port-forward -n fraud-detection-training svc/fraud-detection-training-service 8002:8002

# In another terminal
curl -X POST "http://localhost:8002/train" \
  -H "Content-Type: application/json" \
  -d @training_config.json
```

## Step-by-Step Setup

### Step 1: Create NGC Secret

First, create the NGC API key secret:

```bash
# Replace YOUR_NGC_API_KEY with your actual key
kubectl create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=YOUR_NGC_API_KEY \
  --namespace=fraud-detection-training

# Create Docker registry secret for pulling images
kubectl create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=YOUR_NGC_API_KEY \
  --namespace=fraud-detection-training
```

Or edit `secret.yaml` and apply it:

```bash
kubectl apply -f secret.yaml
```

### Step 2: Upload Training Data

You need to upload your preprocessed data to the PVC:

```bash
# Create PVCs
kubectl apply -f namespace.yaml
kubectl apply -f pvc.yaml

# Create a temporary pod to upload data
kubectl run -n fraud-detection-training data-uploader \
  --image=busybox:1.35 \
  --restart=Never \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "data-uploader",
      "image": "busybox:1.35",
      "command": ["sleep", "3600"],
      "volumeMounts": [{
        "name": "data",
        "mountPath": "/data"
      }]
    }],
    "volumes": [{
      "name": "data",
      "persistentVolumeClaim": {
        "claimName": "fraud-detection-data-pvc"
      }
    }]
  }
}'

# Wait for pod to be ready
kubectl wait --for=condition=ready pod/data-uploader -n fraud-detection-training

# Copy data to PVC
kubectl cp data/TabFormer fraud-detection-training/data-uploader:/data/

# Verify data
kubectl exec -n fraud-detection-training data-uploader -- ls -la /data/TabFormer/gnn

# Clean up uploader pod
kubectl delete pod data-uploader -n fraud-detection-training
```

### Step 3: Deploy Training Job

```bash
# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f pvc.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f job.yaml

# Monitor job progress
kubectl get jobs -n fraud-detection-training -w

# View logs
kubectl logs -f job/fraud-detection-training-job -n fraud-detection-training
```

### Step 4: Retrieve Trained Models

Once training completes:

```bash
# Create a temporary pod to download models
kubectl run -n fraud-detection-training model-downloader \
  --image=busybox:1.35 \
  --restart=Never \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "model-downloader",
      "image": "busybox:1.35",
      "command": ["sleep", "3600"],
      "volumeMounts": [{
        "name": "models",
        "mountPath": "/trained_models"
      }]
    }],
    "volumes": [{
      "name": "models",
      "persistentVolumeClaim": {
        "claimName": "fraud-detection-models-pvc"
      }
    }]
  }
}'

# Wait for pod
kubectl wait --for=condition=ready pod/model-downloader -n fraud-detection-training

# List trained models
kubectl exec -n fraud-detection-training model-downloader -- \
  ls -la /trained_models/python_backend_model_repository/

# Download models
kubectl cp fraud-detection-training/model-downloader:/trained_models ./trained_models

# Clean up
kubectl delete pod model-downloader -n fraud-detection-training
```

## Configuration

### Training Hyperparameters

Edit `configmap.yaml` to adjust training parameters:

```yaml
data:
  training_config.json: |
    {
      "paths": {
        "data_dir": "/data",
        "output_dir": "/trained_models"
      },
      "models": [{
        "kind": "GraphSAGE_XGBoost",
        "gpu": "single",
        "hyperparameters": {
          "gnn": {
            "hidden_channels": 16,    # Embedding dimension
            "n_hops": 1,               # Number of GNN layers
            "dropout_prob": 0.1,       # Dropout rate
            "batch_size": 1024,        # Training batch size
            "fan_out": 16,             # Neighbor sampling
            "num_epochs": 16           # Training epochs
          },
          "xgb": {
            "max_depth": 6,            # Tree depth
            "learning_rate": 0.2,      # Learning rate
            "num_parallel_tree": 3,    # Parallel trees
            "num_boost_round": 512,    # Number of trees
            "gamma": 0.0               # Regularization
          }
        }
      }]
    }
```

### Resource Limits

Edit `deployment.yaml` or `job.yaml` to adjust resources:

```yaml
resources:
  requests:
    memory: "16Gi"
    cpu: "4"
    nvidia.com/gpu: "1"
  limits:
    memory: "32Gi"
    cpu: "8"
    nvidia.com/gpu: "1"
```

### Storage Size

Edit `pvc.yaml` to adjust storage:

```yaml
resources:
  requests:
    storage: 50Gi  # Increase if needed
```

## Monitoring

### Check Job Status

```bash
# Get job status
kubectl get jobs -n fraud-detection-training

# Get pod status
kubectl get pods -n fraud-detection-training

# Describe job
kubectl describe job fraud-detection-training-job -n fraud-detection-training
```

### View Logs

```bash
# Follow logs
kubectl logs -f job/fraud-detection-training-job -n fraud-detection-training

# Get logs from completed job
kubectl logs job/fraud-detection-training-job -n fraud-detection-training

# Get logs from specific pod
POD_NAME=$(kubectl get pods -n fraud-detection-training -l job-name=fraud-detection-training-job -o jsonpath='{.items[0].metadata.name}')
kubectl logs -f $POD_NAME -n fraud-detection-training
```

### Check Training Progress

```bash
# Exec into pod
kubectl exec -it -n fraud-detection-training \
  $(kubectl get pods -n fraud-detection-training -l app=fraud-detection-training -o jsonpath='{.items[0].metadata.name}') \
  -- /bin/bash

# Inside pod, check output directory
ls -la /trained_models/
```

## Troubleshooting

### Issue: Pod stuck in Pending

**Check GPU availability:**
```bash
kubectl describe node | grep -A 5 "nvidia.com/gpu"
```

**Check node selector:**
```bash
kubectl get nodes --show-labels | grep gpu
```

### Issue: ImagePullBackOff

**Check registry secret:**
```bash
kubectl get secret docker-registry-secret -n fraud-detection-training
```

**Recreate secret:**
```bash
kubectl delete secret docker-registry-secret -n fraud-detection-training
kubectl create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=YOUR_NGC_API_KEY \
  --namespace=fraud-detection-training
```

### Issue: Training fails

**Check logs:**
```bash
kubectl logs -f job/fraud-detection-training-job -n fraud-detection-training
```

**Check data availability:**
```bash
kubectl exec -n fraud-detection-training \
  $(kubectl get pods -n fraud-detection-training -l app=fraud-detection-training -o jsonpath='{.items[0].metadata.name}') \
  -- ls -la /data/TabFormer/gnn
```

### Issue: Out of memory

**Increase memory limits in job.yaml:**
```yaml
resources:
  limits:
    memory: "64Gi"  # Increase as needed
```

## Cleanup

```bash
# Delete job
kubectl delete job fraud-detection-training-job -n fraud-detection-training

# Delete deployment (if using server mode)
kubectl delete deployment fraud-detection-training -n fraud-detection-training

# Delete service
kubectl delete service fraud-detection-training-service -n fraud-detection-training

# Delete PVCs (WARNING: This deletes data!)
kubectl delete pvc fraud-detection-data-pvc fraud-detection-models-pvc -n fraud-detection-training

# Delete namespace (deletes everything)
kubectl delete namespace fraud-detection-training
```

## Next Steps

After training completes:

1. **Retrieve trained models** from the models PVC
2. **Deploy inference server** using `k8s/inference-only/`
3. **Test predictions** using the inference API

See `k8s/inference-only/README.md` for inference deployment instructions.
