# OpenShift Deployment Guide - Training

This guide covers deploying the fraud detection training job on OpenShift.

## Prerequisites

- OpenShift cluster with GPU support (NVIDIA GPU Operator installed)
- `oc` CLI tool installed and configured
- NGC API key from NVIDIA
- Preprocessed training data

## OpenShift-Specific Considerations

### 1. Security Context Constraints (SCC)

OpenShift enforces stricter security policies than standard Kubernetes. The manifests are configured to work with the `restricted` SCC:

- Runs as non-root user
- No privilege escalation
- Drops all capabilities
- Uses seccomp profile

### 2. Routes vs Services

OpenShift uses **Routes** instead of Ingress or NodePort for external access:

```yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: fraud-detection-training-route
spec:
  to:
    kind: Service
    name: fraud-detection-training-service
  tls:
    termination: edge
```

### 3. Image Registry

OpenShift can pull from NGC registry with proper credentials:

```bash
oc create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=$NGC_API_KEY \
  -n fraud-detection

# Link secret to service account
oc secrets link default docker-registry-secret --for=pull -n fraud-detection
```

## Quick Deploy on OpenShift

### Step 1: Login to OpenShift

```bash
# Login to your OpenShift cluster
oc login --token=YOUR_TOKEN --server=https://api.your-cluster.com:6443

# Or with username/password
oc login -u your-username -p your-password https://api.your-cluster.com:6443
```

### Step 2: Create/Use Namespace

```bash
# Create namespace (if not exists)
oc apply -f namespace.yaml

# Or use existing namespace
oc project fraud-detection
```

### Step 3: Create Secrets

```bash
# Set your NGC API key
export NGC_API_KEY="your_ngc_api_key_here"

# Create NGC API key secret
oc create secret generic ngc-api-key \
  --from-literal=NGC_API_KEY=$NGC_API_KEY \
  -n fraud-detection

# Create Docker registry secret
oc create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=$NGC_API_KEY \
  -n fraud-detection

# Link secret to default service account
oc secrets link default docker-registry-secret --for=pull -n fraud-detection
```

### Step 4: Create PVCs

```bash
# Check available storage classes
oc get storageclass

# Edit pvc.yaml to use appropriate storage class
# For OpenShift Container Storage:
#   storageClassName: ocs-storagecluster-ceph-rbd
# For AWS EBS:
#   storageClassName: gp2

# Create PVCs
oc apply -f pvc.yaml

# Verify PVCs
oc get pvc -n fraud-detection
```

### Step 5: Upload Training Data

```bash
# Create temporary pod for data upload
oc run -n fraud-detection data-uploader \
  --image=registry.access.redhat.com/ubi8/ubi-minimal:latest \
  --restart=Never \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "data-uploader",
      "image": "registry.access.redhat.com/ubi8/ubi-minimal:latest",
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
oc wait --for=condition=ready pod/data-uploader -n fraud-detection --timeout=120s

# Copy data to PVC
oc cp data/TabFormer fraud-detection/data-uploader:/data/

# Verify data
oc exec -n fraud-detection data-uploader -- ls -la /data/TabFormer/gnn

# Clean up
oc delete pod data-uploader -n fraud-detection
```

### Step 6: Create ConfigMap

```bash
oc apply -f configmap.yaml
```

### Step 7: Deploy Training Job

```bash
# Deploy the training job
oc apply -f job.yaml

# Monitor job status
oc get jobs -n fraud-detection -w

# View logs
oc logs -f job/fraud-detection-training-job -n fraud-detection

# Get pod name
POD_NAME=$(oc get pods -n fraud-detection -l job-name=fraud-detection-training-job -o jsonpath='{.items[0].metadata.name}')

# Follow pod logs
oc logs -f $POD_NAME -n fraud-detection
```

## Alternative: Deploy Training Server

If you want a long-running server for multiple training runs:

```bash
# Deploy server
oc apply -f deployment.yaml
oc apply -f service.yaml

# Wait for deployment
oc rollout status deployment/fraud-detection-training -n fraud-detection

# Get route URL
ROUTE_URL=$(oc get route fraud-detection-training-route -n fraud-detection -o jsonpath='{.spec.host}')
echo "Training API available at: https://$ROUTE_URL"

# Trigger training
curl -X POST "https://$ROUTE_URL/train" \
  -H "Content-Type: application/json" \
  -d @configmap.yaml
```

## GPU Configuration

### Verify GPU Availability

```bash
# Check if GPU operator is installed
oc get pods -n nvidia-gpu-operator

# Check GPU nodes
oc get nodes -l nvidia.com/gpu.present=true

# Describe GPU node
oc describe node <gpu-node-name> | grep -A 10 "Allocatable"
```

### GPU Node Selector

The manifests use this node selector:

```yaml
nodeSelector:
  nvidia.com/gpu.present: "true"
```

If your cluster uses different labels, update the manifests:

```bash
# Check your GPU node labels
oc get nodes --show-labels | grep gpu

# Update node selector in job.yaml and deployment.yaml
```

## Monitoring

### Check Job Status

```bash
# Get job status
oc get jobs -n fraud-detection

# Get job details
oc describe job fraud-detection-training-job -n fraud-detection

# Get pod status
oc get pods -n fraud-detection -l job-name=fraud-detection-training-job
```

### View Logs

```bash
# Follow logs
oc logs -f job/fraud-detection-training-job -n fraud-detection

# Get logs from completed job
oc logs job/fraud-detection-training-job -n fraud-detection

# View events
oc get events -n fraud-detection --sort-by='.lastTimestamp'
```

### Access Pod

```bash
# Get pod name
POD_NAME=$(oc get pods -n fraud-detection -l app=fraud-detection-training -o jsonpath='{.items[0].metadata.name}')

# Exec into pod
oc exec -it $POD_NAME -n fraud-detection -- /bin/bash

# Check training progress
oc exec -n fraud-detection $POD_NAME -- ls -la /trained_models/
```

## Retrieve Trained Models

```bash
# Create downloader pod
oc run -n fraud-detection model-downloader \
  --image=registry.access.redhat.com/ubi8/ubi-minimal:latest \
  --restart=Never \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "model-downloader",
      "image": "registry.access.redhat.com/ubi8/ubi-minimal:latest",
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
oc wait --for=condition=ready pod/model-downloader -n fraud-detection --timeout=120s

# List models
oc exec -n fraud-detection model-downloader -- \
  ls -la /trained_models/python_backend_model_repository/

# Download models
oc cp fraud-detection/model-downloader:/trained_models ./trained_models

# Clean up
oc delete pod model-downloader -n fraud-detection
```

## Troubleshooting

### Issue: ImagePullBackOff

**Check secret:**
```bash
oc get secret docker-registry-secret -n fraud-detection -o yaml
```

**Recreate secret:**
```bash
oc delete secret docker-registry-secret -n fraud-detection
oc create secret docker-registry docker-registry-secret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password=$NGC_API_KEY \
  -n fraud-detection
oc secrets link default docker-registry-secret --for=pull -n fraud-detection
```

### Issue: Pod stuck in Pending (GPU)

**Check GPU availability:**
```bash
oc describe node <gpu-node-name> | grep -A 5 "nvidia.com/gpu"
```

**Check node selector:**
```bash
oc get nodes -l nvidia.com/gpu.present=true
```

**Check GPU operator:**
```bash
oc get pods -n nvidia-gpu-operator
```

### Issue: Permission Denied

**Check SCC:**
```bash
oc get scc
oc describe scc restricted
```

**Check service account:**
```bash
oc get sa default -n fraud-detection -o yaml
```

### Issue: PVC not binding

**Check storage class:**
```bash
oc get storageclass
oc describe storageclass <your-storage-class>
```

**Check PVC status:**
```bash
oc describe pvc fraud-detection-data-pvc -n fraud-detection
```

### Issue: Route not accessible

**Check route:**
```bash
oc get route -n fraud-detection
oc describe route fraud-detection-training-route -n fraud-detection
```

**Test route:**
```bash
ROUTE_URL=$(oc get route fraud-detection-training-route -n fraud-detection -o jsonpath='{.spec.host}')
curl -k https://$ROUTE_URL/health
```

## Resource Quotas

If your namespace has resource quotas, you may need to adjust them:

```bash
# Check quotas
oc get resourcequota -n fraud-detection

# Describe quota
oc describe resourcequota -n fraud-detection

# Request quota increase if needed
```

## Cleanup

```bash
# Delete job only
oc delete job fraud-detection-training-job -n fraud-detection

# Delete deployment (if using server mode)
oc delete deployment fraud-detection-training -n fraud-detection

# Delete service and route
oc delete service fraud-detection-training-service -n fraud-detection
oc delete route fraud-detection-training-route -n fraud-detection

# Delete PVCs (WARNING: This deletes data!)
oc delete pvc fraud-detection-data-pvc fraud-detection-models-pvc -n fraud-detection

# Delete secrets
oc delete secret ngc-api-key docker-registry-secret -n fraud-detection

# Delete namespace (deletes everything)
oc delete project fraud-detection
```

## Next Steps

After training completes:

1. **Retrieve trained models** from the models PVC
2. **Deploy inference server** using `../inference-only/`
3. **Test predictions** using the inference API

See `../inference-only/OPENSHIFT-DEPLOYMENT.md` for inference deployment on OpenShift.

## Useful OpenShift Commands

```bash
# Get all resources in namespace
oc get all -n fraud-detection

# Get events
oc get events -n fraud-detection --sort-by='.lastTimestamp'

# Get resource usage
oc adm top pods -n fraud-detection
oc adm top nodes

# Debug pod
oc debug pod/<pod-name> -n fraud-detection

# Port forward
oc port-forward -n fraud-detection svc/fraud-detection-training-service 8002:8002

# View logs from all pods
oc logs -l app=fraud-detection-training -n fraud-detection --all-containers=true
```
