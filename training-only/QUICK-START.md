# Quick Start: Training on Kubernetes

## Prerequisites

- Kubernetes cluster with GPU support
- NGC API key from NVIDIA
- Preprocessed training data

## Quick Deploy (5 minutes)

### 1. Set your NGC API key

```bash
export NGC_API_KEY="your_ngc_api_key_here"
```

### 2. Run deployment script

```bash
cd k8s/training-only
bash deploy.sh
```

The script will:
- Create namespace
- Create secrets
- Create PVCs
- Deploy training job
- Show monitoring commands

### 3. Monitor training

```bash
# Watch job status
kubectl get jobs -n fraud-detection-training -w

# View logs
kubectl logs -f job/fraud-detection-training-job -n fraud-detection-training
```

### 4. Retrieve trained models

```bash
# Create downloader pod
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

# Download models
kubectl cp fraud-detection-training/model-downloader:/trained_models ./trained_models

# Clean up
kubectl delete pod model-downloader -n fraud-detection-training
```

## Manual Deploy

If you prefer manual steps:

```bash
# 1. Create namespace
kubectl apply -f namespace.yaml

# 2. Create secrets
kubectl create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  --namespace=fraud-detection-training

kubectl create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=$NGC_API_KEY \
  --namespace=fraud-detection-training

# 3. Create PVCs
kubectl apply -f pvc.yaml

# 4. Upload data (if not already done)
# See README.md for data upload instructions

# 5. Create ConfigMap
kubectl apply -f configmap.yaml

# 6. Deploy training job
kubectl apply -f job.yaml
```

## What Gets Created

```
Namespace: fraud-detection-training
├── PVC: fraud-detection-data-pvc (50Gi)
├── PVC: fraud-detection-models-pvc (20Gi)
├── Secret: ngc-api-key
├── Secret: docker-registry-secret
├── ConfigMap: training-config
└── Job: fraud-detection-training-job
    └── Pod: fraud-detection-training-job-xxxxx
        ├── GPU: 1x NVIDIA GPU
        ├── Memory: 16-32Gi
        └── CPU: 4-8 cores
```

## Expected Output

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

## Troubleshooting

### Job stuck in Pending

Check GPU availability:
```bash
kubectl describe nodes | grep -A 5 "nvidia.com/gpu"
```

### ImagePullBackOff

Verify NGC credentials:
```bash
kubectl get secret docker-registry-secret -n fraud-detection-training -o yaml
```

### Training fails

Check logs:
```bash
kubectl logs job/fraud-detection-training-job -n fraud-detection-training
```

Check data:
```bash
POD=$(kubectl get pods -n fraud-detection-training -l job-name=fraud-detection-training-job -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n fraud-detection-training $POD -- ls -la /data/TabFormer/gnn
```

## Cleanup

```bash
# Delete job only
kubectl delete job fraud-detection-training-job -n fraud-detection-training

# Delete everything
kubectl delete namespace fraud-detection-training
```

## Next Steps

1. Deploy inference server: `cd ../inference-only`
2. Test predictions
3. Monitor performance

See `../inference-only/QUICK-START.md` for inference deployment.
