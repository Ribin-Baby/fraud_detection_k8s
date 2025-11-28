---

# ✅ Developer Explanation: How Feature Masking + SHAP Mapping Works

This code is responsible for:

1. **Grouping encoded feature columns** into meaningful feature groups.
2. **Creating a feature mask** required by Triton/TorchScript SHAP explainer.
3. **Mapping SHAP output values back to the original feature names** (e.g., "Zip", "City", "Chip", etc.).

This is required because the model receives **expanded/encoded features**, but SHAP values need to be shown at the **original feature level**.

---

# 📌 1. Grouping Columns by Their Original Field

Your model input `nodes` contains columns like:

```
City_0, City_1, City_2,
Zip_0, Zip_1,
Amount,
Errors_0, Errors_1, …
```

These come from one-hot encoding or other preprocessing.

To compute SHAP values per **original input feature**, we must group these columns.

The code does this:

```python
features = list(nodes.columns)
mask_mapping = {}
feature_mask = []
current_group_id = 0
prv_label = ""

for f in features:
    label = f.split("_")[0]   # Get original feature name (prefix)

    if label != prv_label:    # New feature group?
        current_group_id += 1

    feature_mask.append(current_group_id)
    mask_mapping[label] = current_group_id
    prv_label = label
```

### ✔ What this produces:

* `feature_mask`: A list of integers (1,1,1,2,2,3,3,3…)
  Each group ID corresponds to one original feature.

* `mask_mapping`:
  Maps `original feature name → group id`
  Example:

  ```
  {
    "City": 1,
    "Zip": 2,
    "Amount": 3,
    "Errors": 4,
    ...
  }
  ```

This grouping is necessary because SHAP needs a **mask** that tells which encoded features belong to which original feature.

---

# ----------------------------------------------------

# 🚀 **2. Triton Inference Call (Required for SHAP)**

# ----------------------------------------------------

To request SHAP values from Triton, **you MUST send four inputs**:

1. `NODE_FEATURES`
2. `EDGE_INDEX`
3. `COMPUTE_SHAP`
4. `FEATURE_MASK`

And the model must return **two outputs**:

* `PREDICTION`
* `SHAP_VALUES`

### ✔ Required Triton inference code

```python
# Step 3: Prepare inputs for Triton
input_features = httpclient.InferInput(
    "NODE_FEATURES",
    node_features.shape,
    datatype="FP32"
)
input_features.set_data_from_numpy(node_features)

input_edge_indices = httpclient.InferInput(
    "EDGE_INDEX",
    edge_index.shape,
    datatype="INT64"
)
input_edge_indices.set_data_from_numpy(edge_index)

# SHAP configuration
compute_shap_flag = httpclient.InferInput(
    "COMPUTE_SHAP",
    (1,),
    datatype="BOOL"
)
compute_shap_flag.set_data_from_numpy(compute_shap)

# Feature mask (required when compute_shap = True)
if compute_shap and feature_mask is not None:
    assert nodes.shape[1] == len(feature_mask)
    feature_mask_input = np.array(feature_mask).astype(np.int32)
else:
    feature_mask_input = np.zeros(nodes.shape[1], dtype=np.int32)

input_feature_mask = httpclient.InferInput(
    "FEATURE_MASK",
    feature_mask_input.shape,
    datatype="INT32"
)
input_feature_mask.set_data_from_numpy(feature_mask_input)

# Step 4: Call Triton inference server
outputs = [
    httpclient.InferRequestedOutput("PREDICTION"),
    httpclient.InferRequestedOutput("SHAP_VALUES")
]

with httpclient.InferenceServerClient(f"{self.host}:{self.http_port}") as client:
    response = client.infer(
        self.model_name,
        inputs=[input_features, input_edge_indices, compute_shap_flag, input_feature_mask],
        request_id=str(1),
        outputs=outputs,
        timeout=3000
    )
```
---

# 📌 3. Processing SHAP Values Returned by the Model

When Triton returns:

```python
shap_values = response.as_numpy('SHAP_VALUES')
```

It gives SHAP values **per group ID**, not per column.

Example shape may be `(num_samples, num_groups)`.

Your code picks the SHAP values for the third output (index = 2):

```python
feature_to_attribution_map = dict(
    zip(feature_mask, shap_values[2])
)
```

This creates a mapping:

```
group_id → shap_value
```

Example:

```
{
 1: 0.285,
 2: 0.458,
 3: 0.058,
 4: 0.071,
 ...
}
```

---

# 📌 4. Mapping Back to Original Feature Names

SHAP returns results in **group IDs**, but developers need:

```
"City": 0.285
"Zip": 0.458
...
```

To reverse-lookup names from `mask_mapping`, we invert the dictionary:

```python
feature_name_to_id_map = {v: k for k, v in mask_mapping.items()}
```

Then create the final human-readable SHAP output:

```python
shap_to_features = {
    feature_name_to_id_map[k]: f"{v:.3f}"
    for k, v in feature_to_attribution_map.items()
}
```

### ✔ Final output example:

```json
{
 "Amount": "0.058",
 "Card": "-0.011",
 "Chip": "0.131",
 "City": "0.285",
 "Errors": "0.071",
 "MCC": "-0.064",
 "Merchant": "0.056",
 "Zip": "0.458"
}
```

---

# 🧠 🎯 What This Entire Pipeline Achieves

### **1. Combines multiple encoded columns back into their original feature**

* e.g., `City_0, City_1, City_2 → "City"`

### **2. Sends feature mask to Triton for grouped SHAP**

* Ensures SHAP values are computed per logical feature.

### **3. Maps SHAP output back to original feature names**

* So developers and business users can understand what's happening.

---

# 📘 Developer-Friendly Summary (You Can Copy/Paste This)

**Purpose:**
This code groups preprocessed model input columns into original feature groups and maps the SHAP values returned by Triton to the corresponding human-readable feature names.

**How it works:**

1. **Builds a `feature_mask`** where each original feature gets a unique group ID.
2. **Sends this mask to the SHAP explainer** so SHAP is computed per feature group.
3. **Receives SHAP output grouped by IDs**.
4. **Reconstructs original feature names** using `mask_mapping`.
5. **Produces final SHAP values** like:

   ```
   {"City": 0.285, "Zip": 0.458, "Amount": 0.058}
   ```

---

This is the final interpretable SHAP explanation.

---

# 🎯 **Final Summary for Developers**

### To enable SHAP values in production inference:

---

## **(1) Build a feature mask**

* Group all encoded columns by original feature name.
* Generate `feature_mask` and `mask_mapping`.

---

## **(2) Send these inputs to Triton**

* `NODE_FEATURES`
* `EDGE_INDEX`
* `COMPUTE_SHAP=True`
* `FEATURE_MASK` = feature_mask array

---

## **(3) Request these outputs**

* `"PREDICTION"`
* `"SHAP_VALUES"`

---

## **(4) Convert Triton’s SHAP output to human labels**

* Use `mask_mapping` to map group IDs → feature names.
* Produce final readable JSON.

---
