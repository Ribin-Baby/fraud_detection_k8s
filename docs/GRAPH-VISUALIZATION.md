# Graph Conversion - Visual Guide

## From Tabular Data to Graph

### Input: Tabular Transaction Data

```
┌──────────────────────────────────────────────────────────────────┐
│                    Transaction Table (CSV)                        │
├────────┬─────────┬───────────┬────────┬─────┬───────┬───────────┤
│ User   │ Card    │ Merchant  │ Amount │ MCC │ Time  │ Fraud     │
├────────┼─────────┼───────────┼────────┼─────┼───────┼───────────┤
│ Alice  │ Card123 │ Starbucks │ $4.50  │5812 │ 14:30 │ No        │
│ Bob    │ Card456 │ Amazon    │ $99.99 │5999 │ 09:15 │ No        │
│ Alice  │ Card123 │ Shell Gas │ $45.00 │5541 │ 18:20 │ No        │
│ Carol  │ Card789 │ Walmart   │ $150   │5411 │ 11:00 │ Yes       │
└────────┴─────────┴───────────┴────────┴─────┴───────┴───────────┘
```

### Output: Tri-Partite Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Graph Representation                         │
└─────────────────────────────────────────────────────────────────────┘

    USERS                TRANSACTIONS              MERCHANTS
    (Nodes)              (Nodes)                   (Nodes)

    ┌─────┐              ┌──────────┐              ┌──────────┐
    │Alice│──────────────→│   TX1    │─────────────→│Starbucks │
    │ ID:0│              │$4.50,5812│              │  ID:1000 │
    └─────┘              │14:30     │              └──────────┘
       ↑                 │Fraud: No │                    ↓
       │                 └──────────┘                    │
       │                      ↓                          │
       └──────────────────────┴──────────────────────────┘
                         (Bidirectional)

    ┌─────┐              ┌──────────┐              ┌──────────┐
    │ Bob │──────────────→│   TX2    │─────────────→│  Amazon  │
    │ ID:1│              │$99.99    │              │  ID:1001 │
    └─────┘              │5999,9:15 │              └──────────┘
       ↑                 │Fraud: No │                    ↓
       │                 └──────────┘                    │
       └──────────────────────┴──────────────────────────┘

    ┌─────┐              ┌──────────┐              ┌──────────┐
    │Alice│──────────────→│   TX3    │─────────────→│Shell Gas │
    │ ID:0│              │$45.00    │              │  ID:1002 │
    └─────┘              │5541,18:20│              └──────────┘
       ↑                 │Fraud: No │                    ↓
       │                 └──────────┘                    │
       └──────────────────────┴──────────────────────────┘

    ┌─────┐              ┌──────────┐              ┌──────────┐
    │Carol│──────────────→│   TX4    │─────────────→│ Walmart  │
    │ ID:2│              │$150.00   │              │  ID:1003 │
    └─────┘              │5411,11:00│              └──────────┘
       ↑                 │Fraud: YES│                    ↓
       │                 └──────────┘                    │
       └──────────────────────┴──────────────────────────┘
```

## Node ID Assignment

```
┌────────────────────────────────────────────────────────────┐
│              Consecutive Node ID Ranges                     │
└────────────────────────────────────────────────────────────┘

Node Type       ID Range                    Example IDs
─────────────────────────────────────────────────────────────
Users           [0, N_users)                0, 1, 2, ...
Merchants       [N_users, N_users+N_merch)  1000, 1001, 1002, ...
Transactions    [N_users+N_merch, ...)      1500, 1501, 1502, ...

Example with 1000 users, 500 merchants:
├─ User IDs:        0 - 999
├─ Merchant IDs:    1000 - 1499
└─ Transaction IDs: 1500 - ...
```

## Edge Creation (4 Edges per Transaction)

```
For Transaction TX1 (Alice → Starbucks):

    User (Alice)                Transaction (TX1)           Merchant (Starbucks)
    ID: 0                       ID: 1500                    ID: 1000

    Edge 1: User → Transaction
    ┌─────┐                     ┌──────────┐
    │  0  │────────────────────→│   1500   │
    └─────┘                     └──────────┘

    Edge 2: Transaction → Merchant
                                ┌──────────┐               ┌──────────┐
                                │   1500   │──────────────→│   1000   │
                                └──────────┘               └──────────┘

    Edge 3: Transaction → User (Reverse)
    ┌─────┐                     ┌──────────┐
    │  0  │←────────────────────│   1500   │
    └─────┘                     └──────────┘

    Edge 4: Merchant → Transaction (Reverse)
                                ┌──────────┐               ┌──────────┐
                                │   1500   │←──────────────│   1000   │
                                └──────────┘               └──────────┘

Result: Edge List (src, dst)
┌─────┬──────┐
│ src │ dst  │
├─────┼──────┤
│  0  │ 1500 │  ← User to Transaction
│1500 │ 1000 │  ← Transaction to Merchant
│1500 │  0   │  ← Transaction to User
│1000 │ 1500 │  ← Merchant to Transaction
└─────┴──────┘
```

## Feature Matrix (Block Diagonal)

```
┌────────────────────────────────────────────────────────────────┐
│                    Node Feature Matrix                          │
└────────────────────────────────────────────────────────────────┘

         User Features  │ Merchant Features │ Transaction Features
         (20 dims)      │    (15 dims)      │     (50 dims)
    ─────────────────────────────────────────────────────────────
    User 0    [U0 features]  │      [0]      │        [0]
    User 1    [U1 features]  │      [0]      │        [0]
    User 2    [U2 features]  │      [0]      │        [0]
    ─────────────────────────────────────────────────────────────
    Merch 1000    [0]        │ [M0 features] │        [0]
    Merch 1001    [0]        │ [M1 features] │        [0]
    Merch 1002    [0]        │ [M2 features] │        [0]
    ─────────────────────────────────────────────────────────────
    TX 1500       [0]        │      [0]      │  [T0 features]
    TX 1501       [0]        │      [0]      │  [T1 features]
    TX 1502       [0]        │      [0]      │  [T2 features]
    TX 1503       [0]        │      [0]      │  [T3 features]
    ─────────────────────────────────────────────────────────────

Each node type has its own feature space (sparse representation)
```

## Label Assignment

```
┌────────────────────────────────────────────────────────────────┐
│                    Node Labels (Fraud)                          │
└────────────────────────────────────────────────────────────────┘

Node ID         Node Type       Label (Fraud)
─────────────────────────────────────────────
0               User            0 (no label)
1               User            0 (no label)
2               User            0 (no label)
...
1000            Merchant        0 (no label)
1001            Merchant        0 (no label)
1002            Merchant        0 (no label)
...
1500            Transaction     0 (not fraud)  ← Only transactions labeled
1501            Transaction     0 (not fraud)
1502            Transaction     0 (not fraud)
1503            Transaction     1 (FRAUD!)     ← Target for prediction
...

Only transaction nodes have labels!
Users and merchants are unlabeled (label = 0)
```

## GNN Message Passing

```
┌────────────────────────────────────────────────────────────────┐
│         How GNN Learns from Graph Structure                     │
└────────────────────────────────────────────────────────────────┘

Step 1: Aggregate neighbor information
    
    Transaction TX1 receives messages from:
    ┌─────────────────────────────────────────┐
    │  User (Alice)    →  TX1  ←  Merchant   │
    │  - User history           - Merchant    │
    │  - Spending pattern       - Category    │
    │  - Location               - Risk level  │
    └─────────────────────────────────────────┘

Step 2: Update transaction representation
    
    TX1 embedding = f(TX1 features + Alice features + Starbucks features)

Step 3: Predict fraud
    
    Fraud score = classifier(TX1 updated embedding)

Example fraud pattern detection:
    
    ┌─────────────────────────────────────────────────────────┐
    │ User (Alice) has normal spending pattern                │
    │      ↓                                                   │
    │ Transaction: $10,000 at unusual merchant                │
    │      ↓                                                   │
    │ Merchant: High-risk category, new merchant              │
    │      ↓                                                   │
    │ GNN aggregates: ANOMALY DETECTED → Fraud = 1           │
    └─────────────────────────────────────────────────────────┘
```

## Complete Example: 4 Transactions

```
Input CSV:
┌───────┬───────────┬────────┬───────┐
│ User  │ Merchant  │ Amount │ Fraud │
├───────┼───────────┼────────┼───────┤
│ Alice │ Starbucks │ $4.50  │ No    │
│ Bob   │ Amazon    │ $99.99 │ No    │
│ Alice │ Shell     │ $45.00 │ No    │
│ Carol │ Walmart   │ $150   │ Yes   │
└───────┴───────────┴────────┴───────┘

Output Graph:
┌──────────────────────────────────────────────────────────┐
│ Nodes: 3 users + 4 merchants + 4 transactions = 11 nodes│
│ Edges: 4 transactions × 4 edges = 16 edges              │
│ Features: 11 nodes × ~85 features = 935 values          │
│ Labels: 4 transaction labels (3 × 0, 1 × 1)             │
└──────────────────────────────────────────────────────────┘

Node IDs:
Users:        0 (Alice), 1 (Bob), 2 (Carol)
Merchants:    3 (Starbucks), 4 (Amazon), 5 (Shell), 6 (Walmart)
Transactions: 7 (TX1), 8 (TX2), 9 (TX3), 10 (TX4)

Edge List (16 edges):
0→7, 7→3, 7→0, 3→7    (Alice → Starbucks)
1→8, 8→4, 8→1, 4→8    (Bob → Amazon)
0→9, 9→5, 9→0, 5→9    (Alice → Shell)
2→10, 10→6, 10→2, 6→10 (Carol → Walmart)
```

## Why This Works for Fraud Detection

```
┌────────────────────────────────────────────────────────────────┐
│              Fraud Pattern Examples                             │
└────────────────────────────────────────────────────────────────┘

Pattern 1: Unusual User Behavior
    User (normal spending) → Transaction ($10,000) → Merchant
    GNN detects: Amount anomaly relative to user history

Pattern 2: Risky Merchant
    User → Transaction → Merchant (many fraud transactions)
    GNN detects: Merchant has high fraud rate

Pattern 3: Velocity Attack
    User → Multiple Transactions (short time) → Different Merchants
    GNN detects: Unusual transaction frequency

Pattern 4: Geographic Anomaly
    User (CA) → Transaction (NY) → Transaction (TX) (same hour)
    GNN detects: Impossible travel pattern

The graph structure allows GNN to learn these complex patterns!
```

## Summary

1. **Tabular → Graph**: Each transaction becomes a node connected to user and merchant
2. **Tri-partite**: Three node types with different feature spaces
3. **Bidirectional**: 4 edges per transaction for information flow
4. **Sparse Features**: Block diagonal keeps node types separate
5. **Transaction Labels**: Only transactions are labeled for fraud detection
6. **GNN Learning**: Aggregates information from neighbors to detect fraud patterns

This graph representation enables powerful relational learning that traditional ML cannot achieve!
