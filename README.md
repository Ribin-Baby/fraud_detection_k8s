# OpenShift Kubernetes Deployment

This directory contains Kubernetes manifests and Helm charts for deploying the NVIDIA Financial Fraud Detection inference server on OpenShift.

## 🎯 Deployment Options

### Option 1: Helm Chart (Recommended) ⭐
**Use Helm for easy deployment, upgrades, and rollbacks.**

- ✅ Templated configurations
- ✅ Easy upgrades and rollbacks
- ✅ Environment-specific values
- ✅ Version management

👉 **[Helm Chart: helm-chart/](helm-chart/)** - Production-ready Helm deployment

### Option 2: Plain Kubernetes Manifests
**Use kubectl/oc apply for simple deployments.**

- ✅ Simple and straightforward
- ✅ No additional tools needed
- ✅ Direct YAML control
- ✅ Quick start

👉 **[Kubernetes Manifests: inference-only/](inference-only/)** - 5-minute deployment

---

## Overview (Full Pipeline)

The full deployment architecture includes:
- **Training Job**: Batch job for model training using NVIDIA financial-fraud-training container
- **Inference Deployment**: Scalable deployment of NVIDIA Triton Inference Server
- **Persistent Storage**: PVCs for training data and model repository
- **External Access**: OpenShift Route with TLS for HTTPS access
- **GPU Support**: NVIDIA GPU Operator integration for GPU workloads

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenShift Cluster                         │
│                                                               │
│  ┌──────────────┐         ┌────────────────┐                │
│  │  Data PVC    │         │ Model Repo PVC │                │
│  │  (10GB RWX)  │         │  (5GB RWX)     │                │
│  └──────┬───────┘         └────────┬───────┘                │
│         │                          │                         │
│  ┌──────▼──────────────────────────▼────────┐               │
│  │        Training Job (GPU)                 │               │
│  │  financial-fraud-training:1.0.1           │               │
│  └───────────────────────────────────────────┘               │
│                     │                                         │
│                     │ Produces models                         │
│                     ▼                                         │
│  ┌──────────────────────────────────────────┐                │
│  │    Inference Deployment (GPU)             │                │
│  │    tritonserver:25.04-py3                 │                │
│  │    Replicas: 1-3                          │                │
│  └────────┬─────────────────────────────────┘                │
│           │                                                   │
│  ┌────────▼────────────────────────────────┐                 │
│  │    Service (ClusterIP)                  │                 │
│  │    HTTP:8005 gRPC:8006 Metrics:8007     │                 │
│  └────────┬────────────────────────────────┘                 │
│           │                                                   │
│  ┌────────▼────────────────────────────────┐                 │
│  │    Route (External HTTPS Access)        │                 │
│  └─────────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
k8s/
├── base/                          # Base Kubernetes manifests
│   ├── namespace.yaml             # Namespace definition
│   ├── pvcs.yaml                  # PersistentVolumeClaims
│   ├── training-configmap.yaml    # Training configuration
│   ├── preprocessing-job.yaml     # Data preprocessing job
│   ├── training-job.yaml          # Model training job
│   ├── inference-deployment.yaml  # Triton inference deployment
│   ├── inference-service.yaml     # Service for inference
│   ├── inference-route.yaml       # OpenShift Route
│   ├── kustomization.yaml         # Kustomize base config
│   └── secrets-README.md          # Secret creation guide
├── overlays/                      # Environment-specific configs
│   ├── dev/                       # Development environment
│   │   ├── kustomization.yaml
│   │   ├── resource-patches.yaml
│   │   └── pvc-patches.yaml
│   └── prod/                      # Production environment
│       ├── kustomization.yaml
│       ├── resource-patches.yaml
│       └── pvc-patches.yaml
├── config/                        # Configuration files
│   └── training_config.json      # Training hyperparameters
├── docs/                          # Documentation
│   ├── WORKFLOW.md                # ⭐ Sequential deployment workflow
│   ├── PREREQUISITES.md           # Prerequisites guide
│   ├── INSTALLATION.md            # Installation guide
│   └── OPERATIONS.md              # Operations guide
├── DEPLOYMENT-SUMMARY.md          # Quick reference guide
└── README.md                      # This file
```


## Deployment Workflow

⚠️ **Important**: The deployment follows a **sequential 3-phase workflow**:

```
Phase 1: Data Preprocessing → Phase 2: Model Training → Phase 3: Inference Deployment
```

Each phase must complete before proceeding to the next. See [WORKFLOW.md](docs/WORKFLOW.md) for detailed steps.

## Quick Start

### Prerequisites
- OpenShift 4.12+ cluster with GPU nodes
- NVIDIA GPU Operator installed
- Storage class with ReadWriteMany support
- NGC API key from NVIDIA
- TabFormer dataset downloaded

### Deploy

```bash
# 1. Set NGC API key
export NGC_API_KEY="your-ngc-api-key"

# 2. Create namespace and secrets
oc create namespace fraud-detection
oc create secret docker-registry ngc-secret \
  --docker-server=nvcr.io --docker-username='$oauthtoken' \
  --docker-password="${NGC_API_KEY}" -n fraud-detection
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY="${NGC_API_KEY}" -n fraud-detection

# 3. Deploy infrastructure
oc apply -k k8s/base/

# 4. PHASE 1: Upload and preprocess data
# (Upload raw data to PVC - see WORKFLOW.md)
oc apply -f k8s/base/preprocessing-job.yaml
oc wait --for=condition=Complete job/fraud-detection-preprocessing -n fraud-detection

# 5. PHASE 2: Train model
oc apply -f k8s/base/training-job.yaml
oc logs -f job/fraud-detection-training -n fraud-detection
oc wait --for=condition=Complete job/fraud-detection-training -n fraud-detection

# 6. PHASE 3: Verify inference service
oc wait --for=condition=Available deployment/fraud-detection-inference -n fraud-detection
INFERENCE_URL=$(oc get route fraud-detection-inference -n fraud-detection -o jsonpath='{.spec.host}')
curl -k https://${INFERENCE_URL}/v2/health/ready
```

## Environment Deployments

### Development
```bash
# Deploy with reduced resources
oc apply -k k8s/overlays/dev/
```

**Configuration**:
- Data PVC: 5Gi
- Models PVC: 2Gi
- Training: 2 CPU, 8Gi memory, 1 GPU
- Inference: 1 replica, 1 CPU, 4Gi memory, 1 GPU

### Production
```bash
# Deploy with full resources
oc apply -k k8s/overlays/prod/
```

**Configuration**:
- Data PVC: 20Gi
- Models PVC: 10Gi
- Training: 4 CPU, 16Gi memory, 1 GPU
- Inference: 3 replicas, 2 CPU, 8Gi memory, 1 GPU each

## Key Components

### Training Job
- **Image**: `nvcr.io/nvidia/cugraph/financial-fraud-training:1.0.1`
- **Purpose**: Train GraphSAGE + XGBoost fraud detection model
- **GPU**: 1x NVIDIA GPU (32GB+ memory)
- **Input**: Preprocessed TabFormer data from Data PVC
- **Output**: Trained models to Model Repository PVC
- **Duration**: ~30-60 minutes depending on data size

### Inference Deployment
- **Image**: `nvcr.io/nvidia/tritonserver:25.04-py3`
- **Purpose**: Serve trained models for real-time fraud detection
- **GPU**: 1x NVIDIA GPU per replica
- **Replicas**: 1 (dev) to 3 (prod), scalable
- **Endpoints**:
  - HTTP: Port 8005
  - gRPC: Port 8006
  - Metrics: Port 8007

### Persistent Storage
- **Data PVC**: Stores TabFormer dataset (raw and preprocessed)
- **Model Repository PVC**: Stores trained models and Triton configuration
- **Access Mode**: ReadWriteMany (RWX) for concurrent access
- **Shared**: Both training and inference access model repository

### External Access
- **Route**: HTTPS access via OpenShift Route
- **TLS**: Edge termination with automatic certificates
- **URL**: `https://fraud-detection-inference-fraud-detection.apps.<cluster-domain>`

## Configuration

### Training Configuration
Edit `k8s/config/training_config.json` to adjust:
- Model type (GraphSAGE_XGBoost)
- GNN hyperparameters (hidden channels, epochs, batch size)
- XGBoost hyperparameters (max depth, learning rate)

### Resource Allocation
Modify resource requests/limits in:
- `k8s/base/training-job.yaml` - Training resources
- `k8s/base/inference-deployment.yaml` - Inference resources
- `k8s/overlays/*/resource-patches.yaml` - Environment-specific overrides

### Storage Sizes
Adjust PVC sizes in:
- `k8s/base/pvcs.yaml` - Base sizes
- `k8s/overlays/*/pvc-patches.yaml` - Environment-specific sizes


## Common Operations

### View Status
```bash
# All resources
oc get all -n fraud-detection

# Pods
oc get pods -n fraud-detection

# PVCs
oc get pvc -n fraud-detection

# Events
oc get events -n fraud-detection --sort-by='.lastTimestamp'
```

### View Logs
```bash
# Training logs
oc logs -f job/fraud-detection-training -n fraud-detection

# Inference logs
oc logs -f deployment/fraud-detection-inference -n fraud-detection

# Specific pod
oc logs <pod-name> -n fraud-detection
```

### Scale Inference
```bash
# Scale up
oc scale deployment fraud-detection-inference --replicas=3 -n fraud-detection

# Scale down
oc scale deployment fraud-detection-inference --replicas=1 -n fraud-detection
```

### Retrain Model
```bash
# Delete old training job
oc delete job fraud-detection-training -n fraud-detection

# Create new training job
oc apply -f k8s/base/training-job.yaml

# Restart inference to load new models
oc rollout restart deployment/fraud-detection-inference -n fraud-detection
```

### Test Inference
```bash
# Get route URL
INFERENCE_URL=$(oc get route fraud-detection-inference -n fraud-detection -o jsonpath='{.spec.host}')

# Health check
curl -k https://${INFERENCE_URL}/v2/health/live

# List models
curl -k https://${INFERENCE_URL}/v2/models

# Inference request (requires proper payload)
curl -k -X POST https://${INFERENCE_URL}/v2/models/prediction_and_shapley/infer \
  -H "Content-Type: application/json" \
  -d @test-payload.json
```

## Monitoring

### Metrics
```bash
# Access Prometheus metrics
curl -k https://${INFERENCE_URL}:8007/metrics
```

**Key Metrics**:
- `nv_inference_request_success` - Successful requests
- `nv_inference_request_failure` - Failed requests
- `nv_inference_request_duration_us` - Request latency
- `nv_gpu_utilization` - GPU utilization %
- `nv_gpu_memory_used_bytes` - GPU memory usage

### Resource Usage
```bash
# Pod resource usage
oc adm top pods -n fraud-detection

# Node resource usage
oc adm top nodes

# GPU utilization
oc exec <inference-pod> -n fraud-detection -- nvidia-smi
```

## Troubleshooting

### Pod Not Starting
```bash
# Check pod status
oc describe pod <pod-name> -n fraud-detection

# Common issues:
# - PVC not bound: Check storage class
# - GPU not available: Check GPU Operator
# - Image pull error: Verify NGC secret
```

### Training Job Fails
```bash
# View logs
oc logs job/fraud-detection-training -n fraud-detection

# Common issues:
# - Data not found: Verify data upload
# - OOM: Increase memory limits
# - GPU error: Check GPU availability
```

### Inference Not Ready
```bash
# Check deployment
oc describe deployment fraud-detection-inference -n fraud-detection

# Check logs
oc logs -l component=inference -n fraud-detection

# Common issues:
# - Model not found: Verify training completed
# - Health probe failing: Check model loading
```

## Documentation

- **[Workflow](docs/WORKFLOW.md)**: ⭐ **START HERE** - Sequential deployment workflow
- **[Prerequisites](docs/PREREQUISITES.md)**: System requirements and setup
- **[Installation](docs/INSTALLATION.md)**: Step-by-step deployment guide
- **[Operations](docs/OPERATIONS.md)**: Day-to-day operations and maintenance

## Security Considerations

- **Secrets**: NGC API key stored in Kubernetes Secrets
- **RBAC**: Use appropriate role bindings for access control
- **Network**: Route provides TLS encryption for external access
- **Images**: Pull from trusted NVIDIA NGC registry
- **Storage**: PVCs isolated per namespace

## Performance Tuning

### Inference Optimization
- Scale replicas based on load
- Adjust resource limits for optimal GPU utilization
- Use HPA for automatic scaling
- Monitor latency and throughput metrics

### Training Optimization
- Adjust batch size and epochs in training config
- Use larger GPU for faster training
- Optimize data preprocessing

## Backup and Recovery

### Backup
```bash
# PVC snapshots (if supported)
oc create volumesnapshot fraud-detection-data-snapshot \
  --volumesnapshotclass=<class> \
  --pvc=fraud-detection-data -n fraud-detection

# Export configurations
oc get all,pvc,configmap,route -n fraud-detection -o yaml > backup.yaml
```

### Restore
```bash
# Restore from snapshot
oc apply -f pvc-from-snapshot.yaml

# Restore configurations
oc apply -f backup.yaml
```

## Uninstall

```bash
# Delete all resources
oc delete -k k8s/base/

# Or delete namespace (removes everything)
oc delete namespace fraud-detection
```

## Support

For issues or questions:
- Review documentation in `docs/` directory
- Check OpenShift and NVIDIA documentation
- Review logs and events for error messages
- Open an issue in the repository

## License

See [LICENSE](../LICENSE) file in the repository root.

## References

- [NVIDIA Financial Fraud Detection Blueprint](https://catalog.ngc.nvidia.com/)
- [NVIDIA Triton Inference Server](https://docs.nvidia.com/deeplearning/triton-inference-server/)
- [OpenShift Documentation](https://docs.openshift.com/)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/)
