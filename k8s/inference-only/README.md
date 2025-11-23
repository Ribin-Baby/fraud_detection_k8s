# Inference-Only OpenShift Deployment

This deployment focuses **only on the Triton Inference Server** for serving trained fraud detection models on OpenShift. Data preprocessing and model training remain as local Docker-based workflows.

## Architecture

```
Local Environment                    OpenShift Cluster
┌─────────────────────┐             ┌──────────────────────────┐
│                     │             │                          │
│  Data Preprocessing │             │   Inference Deployment   │
│  (Docker/Local)     │             │   - Triton Server        │
│         ↓           │             │   - GPU Support          │
│  Model Training     │   Upload    │   - HTTPS Route          │
│  (Docker/Local)     │─────────────→   - Auto-scaling         │
│         ↓           │   Models    │                          │
│  Trained Models     │             │   External Access        │
│                     │             │   (HTTPS API)            │
└─────────────────────┘             └──────────────────────────┘
```

## Workflow

1. **Local**: Run data preprocessing using Docker (existing notebook workflow)
2. **Local**: Train model using Docker (existing notebook workflow)
3. **Upload**: Copy trained models to OpenShift PVC
4. **Deploy**: Triton Inference Server loads models and serves predictions

## What You Need

### From Local Training
After running your local Docker-based training, you'll have:
```
model_output_dir/
└── python_backend_model_repository/
    └── prediction_and_shapley/
        ├── 1/
        │   ├── embedding_based_xgboost.json
        │   ├── model.py
        │   └── state_dict_gnn_model.pth
        └── config.pbtxt
```

### For OpenShift
- OpenShift cluster with GPU nodes
- NVIDIA GPU Operator installed
- NGC API key
- Storage for models (5-10Gi PVC)

## Quick Deploy

```bash
# 1. Set NGC API key
export NGC_API_KEY="your-ngc-api-key"

# 2. Create namespace and secrets
oc create namespace fraud-detection
oc create secret docker-registry ngc-secret \
  --docker-server=nvcr.io --docker-username='$oauthtoken' \
  --docker-password="${NGC_API_KEY}" -n fraud-detection

# 3. Create PVC for models
oc apply -f pvc.yaml

# 4. Upload trained models
oc apply -f upload-pod.yaml
oc wait --for=condition=Ready pod/model-uploader -n fraud-detection
oc cp ./model_output_dir/python_backend_model_repository \
  fraud-detection/model-uploader:/models/
oc delete pod model-uploader -n fraud-detection

# 5. Deploy inference server
oc apply -f inference-deployment.yaml
oc apply -f inference-service.yaml
oc apply -f inference-route.yaml

# 6. Get inference URL
INFERENCE_URL=$(oc get route fraud-detection-inference -n fraud-detection -o jsonpath='{.spec.host}')
echo "Inference URL: https://${INFERENCE_URL}"

# 7. Test
curl -k https://${INFERENCE_URL}/v2/health/ready
```

## Files Included

- `pvc.yaml` - PersistentVolumeClaim for model storage
- `upload-pod.yaml` - Temporary pod for uploading models
- `inference-deployment.yaml` - Triton Inference Server deployment
- `inference-service.yaml` - Kubernetes Service
- `inference-route.yaml` - OpenShift Route for external access
- `kustomization.yaml` - Kustomize configuration

## Advantages of This Approach

✅ **Simple**: Only deploy what needs to scale (inference)
✅ **Flexible**: Keep existing local training workflow
✅ **Cost-Effective**: Don't pay for GPU during training downtime
✅ **Fast Iteration**: Train locally, deploy inference quickly
✅ **Scalable**: Inference can scale to multiple replicas

## Next Steps

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.
