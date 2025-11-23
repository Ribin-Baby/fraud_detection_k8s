# Tabular to Graph Conversion - Detailed Explanation

This document explains how the TabFormer credit card transaction data (tabular format) is converted into a graph representation for Graph Neural Network (GNN) training.

## Overview

The preprocessing transforms **tabular transaction data** into a **tri-partite graph** where:
- **Nodes** represent Users, Merchants, and Transactions
- **Edges** represent relationships between these entities
- **Features** are encoded numerical representations of transaction attributes

## Input: Tabular Data

### Raw Transaction Record
Each row in the CSV contains:
```
User, Card, Merchant, Amount, MCC, Time, Day, Month, Year, 
State, City, Zip, Errors, Chip, Fraud (label)
```

Example:
```csv
User123, Card456, "Coffee Shop", $45.50, 5812, 14:30, 15, 03, 2019, CA, "San Francisco", 94102, None, Yes, No
```

## Output: Graph Representation

### 1. Graph Structure (Tri-Partite Graph)

```
        Users                Transactions              Merchants
    ┌─────────┐            ┌──────────────┐         ┌──────────┐
    │ User 0  │───────────→│ Transaction 0│────────→│Merchant 0│
    │ User 1  │            │ Transaction 1│         │Merchant 1│
    │ User 2  │←───────────│ Transaction 2│←────────│Merchant 2│
    │   ...   │            │     ...      │         │   ...    │
    └─────────┘            └──────────────┘         └──────────┘
    
    Node IDs:              Node IDs:                Node IDs:
    0 to N_users-1         N_users+N_merchants      N_users to
                           to                       N_users+N_merchants-1
                           N_users+N_merchants+N_tx-1
```

### 2. Node ID Assignment

The script creates **consecutive node IDs** across three groups:

```python
# Node ID Ranges:
Users:        [0, NR_USERS)
Merchants:    [NR_USERS, NR_USERS + NR_MXS)
Transactions: [NR_USERS + NR_MXS, NR_USERS + NR_MXS + NR_TXS)
```

**Example with 1000 users, 500 merchants, 10000 transactions:**
- User IDs: 0-999
- Merchant IDs: 1000-1499
- Transaction IDs: 1500-11499

## Conversion Process

### Step 1: Assign Unique IDs

```python
# Assign consecutive IDs to each entity type
data[COL_TRANSACTION_ID] = data.index  # 0, 1, 2, ...

# Map merchant names to IDs
merchant_name_to_id = dict(
    zip(data[COL_MERCHANT].unique(), 
        np.arange(len(data[COL_MERCHANT].unique())))
)
data[COL_MERCHANT_ID] = data[COL_MERCHANT].map(merchant_name_to_id)

# Map user/card to IDs
id_to_consecutive_id = dict(
    zip(data[COL_CARD].unique(), 
        np.arange(len(data[COL_CARD].unique())))
)
data[COL_USER_ID] = data[COL_CARD].map(id_to_consecutive_id)
```

### Step 2: Create Edges (Relationships)

Each transaction creates **4 directed edges**:

```python
# 1. User → Transaction
U_2_T[COL_GRAPH_SRC] = data[COL_USER_ID]
U_2_T[COL_GRAPH_DST] = data[COL_TRANSACTION_ID] + NR_USERS + NR_MXS

# 2. Transaction → Merchant
T_2_M[COL_GRAPH_SRC] = data[COL_TRANSACTION_ID] + NR_USERS + NR_MXS
T_2_M[COL_GRAPH_DST] = data[COL_MERCHANT_ID] + NR_USERS

# 3. Transaction → User (reverse)
T_2_U[COL_GRAPH_SRC] = data[COL_TRANSACTION_ID] + NR_USERS + NR_MXS
T_2_U[COL_GRAPH_DST] = data[COL_USER_ID]

# 4. Merchant → Transaction (reverse)
M_2_T[COL_GRAPH_SRC] = data[COL_MERCHANT_ID] + NR_USERS
M_2_T[COL_GRAPH_DST] = data[COL_TRANSACTION_ID] + NR_USERS + NR_MXS

# Combine all edges
Edge = cudf.concat([U_2_T, T_2_M, T_2_U, M_2_T])
```

**Why 4 edges per transaction?**
- Bidirectional relationships allow GNN to propagate information in both directions
- User ↔ Transaction: Captures user behavior patterns
- Transaction ↔ Merchant: Captures merchant characteristics

### Step 3: Create Node Features

Each node needs a feature vector. The script creates features for all three node types:

```python
# Transaction features (from original data)
T = transaction_feature_df[columns_of_transformed_data].values

# User features (encoded from user/card attributes)
U = preprocessed_user_data.values

# Merchant features (encoded from merchant attributes)
M = preprocessed_merchant_data.values

# Combine into single feature matrix using block diagonal
# This ensures each node type has its own feature space
node_feature_df = pd.DataFrame(block_diag(U, M, T), columns=combined_cols)
```

**Block Diagonal Structure:**
```
        User Features | Merchant Features | Transaction Features
Users   [   U   ]     [    0    ]        [        0        ]
Merchants[   0   ]     [    M    ]        [        0        ]
Transactions[0  ]     [    0    ]        [        T        ]
```

This creates a sparse feature matrix where:
- Users have features only in "User" columns
- Merchants have features only in "Merchant" columns
- Transactions have features only in "Transaction" columns

### Step 4: Create Node Labels

Only **transaction nodes** have labels (fraud/not fraud):

```python
# Initialize all labels to 0
node_label_df = pd.DataFrame(
    np.zeros(len(node_feature_df), dtype=int), 
    columns=[COL_FRAUD]
)

# Set labels only for transaction nodes
node_label_df.iloc[NR_USERS + NR_MXS : NR_USERS + NR_MXS + NR_TXS, 0] = \
    transaction_feature_df[COL_FRAUD].values
```

## Example Conversion

### Input: Single Transaction
```
User: Alice (ID: 5)
Merchant: Starbucks (ID: 23)
Transaction: $4.50 coffee
Amount: 4.50, Time: 14:30, MCC: 5812
Fraud: No
```

### Output: Graph Elements

**Nodes Created:**
- User node: ID = 5
- Merchant node: ID = 1000 + 23 = 1023
- Transaction node: ID = 1500 + 789 = 2289 (assuming 789th transaction)

**Edges Created:**
```
Edge 1: 5 → 2289      (User Alice → Transaction)
Edge 2: 2289 → 1023   (Transaction → Merchant Starbucks)
Edge 3: 2289 → 5      (Transaction → User Alice)
Edge 4: 1023 → 2289   (Merchant Starbucks → Transaction)
```

**Features:**
- User node 5: [encoded user features, 0, 0, ...]
- Merchant node 1023: [0, encoded merchant features, 0, ...]
- Transaction node 2289: [0, 0, encoded transaction features]

**Label:**
- Transaction node 2289: label = 0 (not fraud)

## Why This Graph Structure?

### 1. Captures Relationships
- **User patterns**: Multiple transactions by same user
- **Merchant patterns**: Multiple transactions at same merchant
- **Transaction context**: Each transaction connects user and merchant

### 2. Enables GNN Learning
- **Message passing**: Information flows through edges
- **Neighborhood aggregation**: Each node learns from connected nodes
- **Pattern detection**: GNN can detect fraud patterns across the graph

### 3. Handles Heterogeneous Data
- Different node types (users, merchants, transactions)
- Different feature spaces for each type
- Relationships between different types

## Output Files

### For GNN Training:
```
gnn/
├── nodes/
│   ├── node.csv                          # Node features
│   ├── node_label.csv                    # Node labels (fraud/not fraud)
│   └── offset_range_of_training_node.json # Transaction node range
└── edges/
    └── node_to_node.csv                  # Edge list (src, dst)
```

### For XGBoost Training:
```
xgb/
├── training.csv      # Flattened features for XGBoost
├── validation.csv
└── test.csv
```

## Key Insights

1. **Tri-partite Graph**: Three node types (users, merchants, transactions) with relationships
2. **Consecutive IDs**: All node IDs are consecutive integers starting from 0
3. **Bidirectional Edges**: Each transaction creates 4 edges for information flow
4. **Sparse Features**: Block diagonal structure keeps node types separate
5. **Transaction Labels**: Only transactions are labeled (fraud detection target)

## Graph Statistics

For a typical dataset:
- **Nodes**: ~10,000 users + ~5,000 merchants + ~1,000,000 transactions = ~1,015,000 nodes
- **Edges**: 4 edges per transaction = ~4,000,000 edges
- **Features**: ~50-100 features per node (depending on encoding)
- **Labels**: ~1,000,000 labels (one per transaction)

## Advantages of Graph Representation

1. **Relational Learning**: Captures relationships between entities
2. **Context Awareness**: Each transaction has context from user and merchant
3. **Pattern Detection**: GNN can detect complex fraud patterns
4. **Scalability**: Efficient sparse representation
5. **Flexibility**: Can add new node/edge types easily

This graph structure enables the GraphSAGE GNN to learn fraud patterns by aggregating information from neighboring nodes (users and merchants) for each transaction!
