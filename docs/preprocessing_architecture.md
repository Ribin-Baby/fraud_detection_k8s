# TabFormer Data Processing Architecture

## 1. High-Level System Architecture

```mermaid
flowchart TB
    subgraph Input
        A[Raw Transaction CSV<br/>24M records, 15 columns]
    end
    
    subgraph "Phase 1: Data Cleaning"
        B[Load with cuDF]
        C[Rename Columns]
        D[Handle Missing Values]
        E[Data Type Conversions]
    end
    
    subgraph "Phase 2: Feature Engineering"
        F[Combine User + Card IDs]
        G[Fit Binary Encoder<br/>Card, Merchant, MCC]
        H[Generate Encoded ID Columns]
        I[Correlation Analysis]
    end
    
    subgraph "Phase 3: Data Splitting"
        J{Temporal Split}
        K[Training<br/>Year < 2018]
        L[Validation<br/>Year = 2018]
        M[Test<br/>Year > 2018]
        N[Under-sampling<br/>Optional]
    end
    
    subgraph "Phase 4A: XGBoost Pipeline"
        O[Select Features]
        P{Encoding Strategy}
        Q[Binary Encoder<br/>High Cardinality]
        R[OneHot Encoder<br/>Low Cardinality]
        S[RobustScaler<br/>Amount]
        T[Fit Transformer<br/>on Training]
        U[Transform All Splits]
    end
    
    subgraph "Phase 4B: GNN Pipeline"
        V[Assign Node IDs]
        W[Apply ID Offsets]
        X[Build Edge List<br/>4 Edge Types]
        Y[Create Feature Matrix<br/>Block Diagonal]
        Z[Generate Node Labels]
    end
    
    subgraph "XGBoost Output"
        AA[training.csv]
        AB[validation.csv]
        AC[test.csv]
    end
    
    subgraph "GNN Output"
        AD[edges/node_to_node.csv]
        AE[nodes/node.csv]
        AF[nodes/node_label.csv]
        AG[test_gnn/edges/]
        AH[test_gnn/nodes/]
    end
    
    A --> B --> C --> D --> E
    E --> F --> G --> H --> I
    I --> J
    J --> K & L & M
    K & L & M --> N
    
    N --> O
    O --> P
    P --> Q & R
    Q & R --> S --> T --> U
    U --> AA & AB & AC
    
    N --> V
    V --> W --> X --> Y --> Z
    Z --> AD & AE & AF
    Z --> AG & AH
    
    style A fill:#e1f5ff
    style AA fill:#c8e6c9
    style AB fill:#c8e6c9
    style AC fill:#c8e6c9
    style AD fill:#fff9c4
    style AE fill:#fff9c4
    style AF fill:#fff9c4
    style AG fill:#fff9c4
    style AH fill:#fff9c4
```

## 2. Detailed XGBoost Pipeline

```mermaid
flowchart LR
    subgraph Input
        A[Training Data<br/>predictor_columns]
    end
    
    subgraph "Feature Categorization"
        B{Count Unique<br/>Values}
        C[≤ 8 categories]
        D[> 8 categories]
    end
    
    subgraph "Encoding"
        E[OneHotEncoder<br/>Chip, Errors]
        F[BinaryEncoder<br/>City, Zip]
        G[RobustScaler<br/>Amount]
    end
    
    subgraph "Column Transformer"
        H[Fit on Training]
        I[Transform Train/Val/Test]
    end
    
    subgraph "ID Features"
        J[Pre-encoded<br/>Card_0...Card_12<br/>Merchant_0...Merchant_16<br/>MCC_0...MCC_6]
    end
    
    subgraph "Final Assembly"
        K[Concatenate:<br/>Encoded Features + ID Features]
        L[Add Fraud Label<br/>as Last Column]
    end
    
    subgraph Output
        M[Encoded CSV<br/>~70 columns]
    end
    
    A --> B
    B --> C --> E
    B --> D --> F
    A --> G
    
    E & F & G --> H --> I
    I --> K
    J --> K
    K --> L --> M
    
    style A fill:#e1f5ff
    style M fill:#c8e6c9
```

## 3. Detailed GNN Pipeline - Graph Construction

```mermaid
flowchart TB
    subgraph "Input Data"
        A[Training + Validation<br/>Transaction Records]
    end
    
    subgraph "Step 1: Node ID Assignment"
        B[Transaction_ID = row_index]
        C[Merchant_ID = map unique merchants]
        D[User_ID = map unique cards]
    end
    
    subgraph "Step 2: Calculate Counts"
        E[NR_USERS = max User_ID + 1]
        F[NR_MXS = max Merchant_ID + 1]
        G[NR_TXS = max Transaction_ID + 1]
    end
    
    subgraph "Step 3: Apply Offsets"
        H[Users: 0 to NR_USERS-1]
        I[Merchants: NR_USERS to NR_USERS+NR_MXS-1]
        J[Transactions: NR_USERS+NR_MXS to end]
    end
    
    subgraph "Step 4: Build Edges COO Format"
        K[User → Transaction<br/>src: User_ID<br/>dst: Tx_ID + offset]
        L[Transaction → Merchant<br/>src: Tx_ID + offset<br/>dst: Merchant_ID + offset]
        M[Transaction → User<br/>src: Tx_ID + offset<br/>dst: User_ID]
        N[Merchant → Transaction<br/>src: Merchant_ID + offset<br/>dst: Tx_ID + offset]
        O[Concatenate All Edges]
    end
    
    subgraph "Step 5: Node Features"
        P[Extract User Features<br/>Card_0...Card_12]
        Q[Extract Merchant Features<br/>Merchant_0...Merchant_16<br/>MCC_0...MCC_6]
        R[Transform Transaction Features<br/>All encoded columns]
        S[Block Diagonal Matrix<br/>U 0 0<br/>0 M 0<br/>0 0 T]
    end
    
    subgraph "Step 6: Node Labels"
        T[Initialize zeros<br/>length = total nodes]
        U[Set Tx labels<br/>indices NR_USERS+NR_MXS:end]
    end
    
    subgraph Output
        V[edges/node_to_node.csv]
        W[nodes/node.csv]
        X[nodes/node_label.csv]
        Y[offset_range.json]
    end
    
    A --> B & C & D
    B & C & D --> E & F & G
    E & F & G --> H & I & J
    H & I & J --> K & L & M & N
    K & L & M & N --> O
    
    A --> P & Q & R
    P & Q & R --> S
    
    A --> T --> U
    
    O --> V
    S --> W
    U --> X
    E & F & G --> Y
    
    style A fill:#e1f5ff
    style V fill:#fff9c4
    style W fill:#fff9c4
    style X fill:#fff9c4
    style Y fill:#fff9c4
```

## 4. Graph Structure Visualization

```mermaid
graph LR
    subgraph "Node ID Space"
        subgraph "Users 0-999"
            U1[User 0]
            U2[User 1]
            U3[User ...]
        end
        
        subgraph "Merchants 1000-1499"
            M1[Merchant 1000]
            M2[Merchant 1001]
            M3[Merchant ...]
        end
        
        subgraph "Transactions 1500-11499"
            T1[Transaction 1500]
            T2[Transaction 1501]
            T3[Transaction ...]
        end
    end
    
    U1 <-->|Edge| T1
    T1 <-->|Edge| M1
    U2 <-->|Edge| T2
    T2 <-->|Edge| M2
    U1 <-->|Edge| T3
    T3 <-->|Edge| M2
    
    style U1 fill:#bbdefb
    style U2 fill:#bbdefb
    style U3 fill:#bbdefb
    style M1 fill:#c8e6c9
    style M2 fill:#c8e6c9
    style M3 fill:#c8e6c9
    style T1 fill:#fff9c4
    style T2 fill:#fff9c4
    style T3 fill:#fff9c4
```

## 5. Feature Matrix Structure (Block Diagonal)

```mermaid
flowchart TB
    subgraph "Node Feature Matrix"
        A["Row 0-999: User Features<br/>[Card_0...Card_12 | zeros for other features]"]
        B["Row 1000-1499: Merchant Features<br/>[zeros | Merchant_0...Merchant_16, MCC_0...MCC_6 | zeros]"]
        C["Row 1500-11499: Transaction Features<br/>[zeros | zeros | All encoded features + Amount]"]
    end
    
    subgraph "Feature Columns ~70 total"
        D[Card Features<br/>13 columns]
        E[Merchant/MCC Features<br/>24 columns]
        F[Transaction Features<br/>~33 columns]
    end
    
    A -.->|Uses| D
    B -.->|Uses| E
    C -.->|Uses| D & E & F
    
    style A fill:#bbdefb
    style B fill:#c8e6c9
    style C fill:#fff9c4
```

## 6. Data Transformation Flow

```mermaid
flowchart LR
    subgraph "Raw Features"
        A1[User: 5]
        A2[Card: 123]
        A3[Merchant: 'Walmart']
        A4[Amount: $100.50]
        A5[Chip: 'Swipe']
        A6[City: 'NYC']
    end
    
    subgraph "Cleaning"
        B1[User*max_cards + Card<br/>= 5*10000 + 123]
        B2[Merchant → str]
        B3[Remove '$' → 100.50]
        B4[Chip → category]
        B5[City → category]
    end
    
    subgraph "Encoding"
        C1[Card → Binary<br/>Card_0...Card_12]
        C2[Merchant → Binary<br/>Merchant_0...Merchant_16]
        C3[Amount → Scaled<br/>-0.234]
        C4[Chip → OneHot<br/>0,0,1]
        C5[City → Binary<br/>City_0...City_13]
    end
    
    subgraph "Final Features"
        D[70-column vector<br/>ready for ML]
    end
    
    A1 & A2 --> B1 --> C1
    A3 --> B2 --> C2
    A4 --> B3 --> C3
    A5 --> B4 --> C4
    A6 --> B5 --> C5
    
    C1 & C2 & C3 & C4 & C5 --> D
    
    style D fill:#c8e6c9
```

## 7. Temporal Data Split Strategy

```mermaid
timeline
    title Data Split by Year
    section 2014-2017
        Training Data : All transactions before 2018
                      : Fit transformers here
                      : Learn encoding mappings
    section 2018
        Validation Data : All transactions in 2018
                        : Tune hyperparameters
                        : Model selection
    section 2019+
        Test Data : All transactions after 2018
                  : Final evaluation
                  : Unseen data
```

## 8. Component Dependencies

```mermaid
graph TD
    A[Raw CSV Data]
    B[id_transformer<br/>BinaryEncoder]
    C[transformer<br/>ColumnTransformer]
    D[Training Data]
    E[Validation Data]
    F[Test Data]
    G[XGBoost Files]
    H[GNN Files]
    
    A -->|Fit| B
    A -->|Split| D & E & F
    D -->|Fit| C
    
    B -->|Transform| D & E & F
    C -->|Transform| D & E & F
    
    D & E & F -->|Format| G
    D & E & F -->|Format| H
    
    B -.->|Save for<br/>Inference| I[Saved Models]
    C -.->|Save for<br/>Inference| I
    
    style B fill:#ffccbc
    style C fill:#ffccbc
    style I fill:#f8bbd0
```

## Key Insights for Architecture

### XGBoost Path
- **Input**: Tabular transaction records
- **Output**: Flat CSV with ~70 encoded columns
- **Key**: Maintains row-level independence

### GNN Path
- **Input**: Same tabular records
- **Output**: Graph structure (nodes + edges + features)
- **Key**: Creates relationships between entities

### Shared Components
- Both paths use the same fitted transformers
- Ensures consistency between XGBoost and GNN features
- Critical for ensemble or comparison

### Inference Requirements
- Must save `id_transformer` and `transformer`
- New data must go through identical preprocessing
- Same encoding mappings must be applied
