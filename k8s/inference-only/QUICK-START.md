# Quick Start - Inference-Only Deployment

Deploy Triton Inference Server to OpenShift in 5 minutes!

## Prerequisites
- ✅ Trained models from local Docker workflow
- ✅ OpenShift cluster with GPU
- ✅ NGC API key

## 5-Minute Deploy

```bash
# 1. Setup (30 seconds)
export NGC_API_KEY="your-key"
oc login --server=https://your-cluster:6443
oc apply -f namespace.yaml
oc create secret docker-registry ngc-secret \
  --docker-server=nvcr.io --docker-username='$oauthtoken' \
  --docker-password="${NGC_API_KEY}" -n fraud-detection

# 2. Create storage (30 seconds)
oc apply -f pvc.yaml
oc get pvc -n fraud-detection -w  # Wait for Bound

# 3. Upload models (2 minutes)
oc apply -f upload-pod.yaml
oc wait --for=condition=Ready pod/model-uploader -n fraud-detection
oc cp ./model_output_dir/python_backend_model_repository \
  fraud-detection/model-uploader:/models/
oc delete pod model-uploader -n fraud-detection

# 4. Deploy inference (2 minutes)
oc apply -k .
oc wait --for=condition=Available deployment/fraud-detection-inference -n fraud-detection

# 5. Test (30 seconds)
INFERENCE_URL=$(oc get route fraud-detection-inference -n fraud-detection -o jsonpath='{.spec.host}')
curl -k https://${INFERENCE_URL}/v2/health/ready
echo "✅ Deployed! URL: https://${INFERENCE_URL}"
```

## Update Models

```bash
# Retrain locally, then:
oc apply -f upload-pod.yaml
oc wait --for=condition=Ready pod/model-uploader -n fraud-detection
oc exec model-uploader -n fraud-detection -- rm -rf /models/python_backend_model_repository
oc cp ./model_output_dir/python_backend_model_repository fraud-detection/model-uploader:/models/
oc delete pod model-uploader -n fraud-detection
oc rollout restart deployment/fraud-detection-inference -n fraud-detection
```

## Scale

```bash
# Scale up
oc scale deployment fraud-detection-inference --replicas=3 -n fraud-detection

# Auto-scale
oc autoscale deployment fraud-detection-inference --min=1 --max=5 --cpu-percent=70 -n fraud-detection
```

## Monitor

```bash
# Status
oc get all -n fraud-detection

# Logs
oc logs -f deployment/fraud-detection-inference -n fraud-detection

# GPU usage
oc exec <pod-name> -n fraud-detection -- nvidia-smi
```

## Use from Python

```python
import requests

INFERENCE_URL = "https://your-route-url"

response = requests.post(
    f"{INFERENCE_URL}/v2/models/prediction_and_shapley/infer",
    json=payload,
    verify=False
)
predictions = response.json()["outputs"][0]["data"]
```

## Files

- `namespace.yaml` - Namespace
- `pvc.yaml` - Storage for models
- `upload-pod.yaml` - Temporary pod for uploads
- `inference-deployment.yaml` - Triton server
- `inference-service.yaml` - Internal service
- `inference-route.yaml` - External HTTPS access
- `kustomization.yaml` - Deploy all at once

## Help

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

## Cleanup

```bash
oc delete namespace fraud-detection
```

That's it! 🎉
