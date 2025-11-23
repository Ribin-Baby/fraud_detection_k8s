# How to Save Transformers Without Modifying preprocess_TabFormer.py

## Problem

The `preprocess_TabFormer.py` script creates and fits transformers but doesn't save them. You need these transformers for single transaction inference, but you don't want to modify the original code.

## Solution: Run Post-Processing Script

### Step 1: Run Original Preprocessing

First, run your preprocessing as normal:

```bash
python src/preprocess_TabFormer.py
```

This creates:
```
data/TabFormer/
├── raw/
│   └── card_transaction.v1.csv
├── xgb/
│   ├── training.csv
│   ├── validation.csv
│   └── test.csv
└── gnn/
    ├── edges/
    └── nodes/
```

### Step 2: Save Transformers

Run the post-processing script to create and save transformers:

```bash
python src/save_transformers_from_data.py --data-path data/TabFormer
```

This will:
1. Load the raw training data
2. Re-fit the transformers (same logic as original)
3. Save them to `data/TabFormer/transformers/`

Output:
```
data/TabFormer/
└── transformers/
    ├── id_transformer.pkl       # BinaryEncoder for Card/Merchant/MCC
    ├── transformer.pkl          # ColumnTransformer for other features
    └── metadata.pkl             # Feature names and dimensions
```

### Step 3: Verify

The script automatically verifies the transformers work:

```
✓ ID transform works: (1, 37)
✓ Feature transform works: (1, 33)
✓ Combined features: (1, 70)
```

## How It Works

The script re-creates the exact same transformers by:

1. **Loading raw data**:
   ```python
   data = pd.read_csv("raw/card_transaction.v1.csv", nrows=100000)
   ```

2. **Applying same cleaning**:
   ```python
   # Same logic as preprocess_TabFormer.py
   data['Amount'] = data['Amount'].str.replace('$', '').astype('float')
   data['Card'] = data['User'] * max_cards + data['Card']
   # ... etc
   ```

3. **Fitting transformers**:
   ```python
   id_transformer = ColumnTransformer(...)
   id_transformer.fit(data_ids)
   
   transformer = ColumnTransformer(...)
   transformer.fit(training_data)
   ```

4. **Saving with pickle**:
   ```python
   pickle.dump(id_transformer, open('id_transformer.pkl', 'wb'))
   pickle.dump(transformer, open('transformer.pkl', 'wb'))
   ```

## Why This Works

- **Same logic**: Uses identical preprocessing steps
- **Same data**: Fits on the same training data (Year < 2018)
- **Same parameters**: Uses same encoding strategies (binary vs one-hot)
- **No modifications**: Original `preprocess_TabFormer.py` unchanged

## Using Saved Transformers

Once saved, use them for single transaction inference:

```python
import pickle

# Load transformers
with open('data/TabFormer/transformers/id_transformer.pkl', 'rb') as f:
    id_transformer = pickle.load(f)

with open('data/TabFormer/transformers/transformer.pkl', 'rb') as f:
    transformer = pickle.load(f)

# Use for inference
from single_transaction_inference import SingleTransactionInference

client = SingleTransactionInference(
    transformer_path='data/TabFormer/transformers/transformer.pkl',
    id_transformer_path='data/TabFormer/transformers/id_transformer.pkl',
    historical_graph_path='data/TabFormer/gnn',
    host='localhost',
    http_port=8000
)

# Predict
result = client.predict_single_transaction(raw_transaction)
```

## Alternative: Modify Return Statement (If Needed)

If you absolutely need the transformers from the original run, you can make a minimal change:

### Original (line ~280):
```python
id_transformer = id_transformer.fit(data_ids)
```

### Modified:
```python
id_transformer = id_transformer.fit(data_ids)

# Save transformer for inference
import pickle
os.makedirs(os.path.join(tabformer_base_path, "transformers"), exist_ok=True)
with open(os.path.join(tabformer_base_path, "transformers", "id_transformer.pkl"), 'wb') as f:
    pickle.dump(id_transformer, f)
```

### Original (line ~380):
```python
transformer = transformer.fit(pdf_training[predictor_columns])
```

### Modified:
```python
transformer = transformer.fit(pdf_training[predictor_columns])

# Save transformer for inference
with open(os.path.join(tabformer_base_path, "transformers", "transformer.pkl"), 'wb') as f:
    pickle.dump(transformer, f)
```

But the post-processing script approach is cleaner and doesn't require any modifications!

## Troubleshooting

### Issue: "File not found"

Make sure you've run the original preprocessing first:
```bash
python src/preprocess_TabFormer.py
```

### Issue: "Dimension mismatch"

The transformers must be fitted on the same data. If you've changed the preprocessing logic, re-run both scripts.

### Issue: "Import error"

Install required packages:
```bash
pip install category-encoders scikit-learn pandas numpy
```

## Summary

**Recommended workflow**:
1. Run original preprocessing: `python src/preprocess_TabFormer.py`
2. Save transformers: `python src/save_transformers_from_data.py --data-path data/TabFormer`
3. Use for inference: Load transformers with `pickle.load()`

**No modifications needed to original code!**
