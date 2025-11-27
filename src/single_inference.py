import json
import os
import numpy as np
import pandas as pd
from scipy.linalg import block_diag
import tritonclient.http as httpclient
from typing import Dict, Tuple, Optional
import pickle


class SingleTransactionInference:
    """
    Handles single transaction inference for the GNN+XGBoost fraud detection model.
    
    This class manages the preprocessing pipeline and graph construction needed
    to score individual transactions using the Triton inference server.
    """
    
    def __init__(
        self,
        TRANSFORMER_DIR: str,
        host: str = "0.0.0.0",
        http_port: int = 8005,
        model_name: str = "prediction_and_shapley"
    ):
        """
        Initialize the inference client.
        
        Parameters:
        -----------
        transformer_path : str
            Path to saved sklearn ColumnTransformer (for features)
        id_transformer_path : str
            Path to saved BinaryEncoder transformer (for Card/Merchant/MCC)
        historical_graph_path : str
            Path to historical graph data (edges and node features)
        host : str
            Triton server host
        http_port : int
            Triton server HTTP port
        model_name : str
            Name of the model in Triton
        """
        self.host = host
        self.http_port = http_port
        self.model_name = model_name
        
        # Load preprocessing transformers
        with open(os.path.join(TRANSFORMER_DIR, "transformer.pkl"), 'rb') as f:
            self.transformer = pickle.load(f)
        with open(os.path.join(TRANSFORMER_DIR, "id_transformer.pkl"), 'rb') as f:
            self.id_transformer = pickle.load(f)
        with open(os.path.join(TRANSFORMER_DIR, "metadata.pkl"), 'rb') as f:
            self.mappings = pickle.load(f)
        with open(os.path.join(TRANSFORMER_DIR, "metadata.json"), "r") as f:
            self.metadata = json.load(f)
        
        # Column definitions (must match preprocessing)
        self.merchant_name_to_id = self.mappings["merchant_name_to_id"]
        self.id_to_consecutive_id = self.mappings["card_to_user_id"]
        # training node counts (optional, saved during training)
        self.NR_USERS_train = self.metadata.get("NR_USERS", None)
        self.NR_MXS_train = self.metadata.get("NR_MXS", None)

        self.predictor_columns = self.metadata.get("predictor_columns", None)
        self.merchant_and_user_cols = self.metadata.get("merchant_and_user_cols", None)
    
    def normalize_row(self, row):
        # apply same cleaning as preprocess: Amount, Time, Fraud mapping etc.
        r = row.copy()
        # Amount e.g. "$280.13"
        if isinstance(r["Amount"], str) and r["Amount"].startswith("$"):
            r["Amount"] = float(r["Amount"].replace("$", ""))
        # Time e.g. "12:55"
        if isinstance(r["Time"], str):
            hh, mm = r["Time"].split(":")
            r["Time"] = int(hh) * 60 + int(mm)
        # Fraud mapping (if present)
        if "Is Fraud?" in r:
            r["Fraud"] = 1 if r["Is Fraud?"] == "Yes" else 0
        r['Merchant'] = str(r.get('Merchant Name', 'Unknown'))
        r['Chip'] = r.get('Use Chip', 'Swipe Transaction')
        r['City'] = r.get('Merchant City', 'Unknown')
        r['State'] = r.get('Merchant State', 'XX')
        r['Errors'] = r.get('Errors?', 'XX').replace(',', '')
        return r

    def convert_single(self, record_dict: Dict):

        # Normalize input row
        r = self.normalize_row(record_dict)

        df = pd.DataFrame([r])

        # ==================
        # Map IDs
        # ==================
        merchant = df.loc[0, "Merchant"]
        card = df.loc[0, "Card"]

        merchant_id = self.merchant_name_to_id.get(str(merchant), -1)
        user_id = self.id_to_consecutive_id.get(card, -1)
        # print("ID:", merchant_id,  user_id)
        # For inference, unseen ID => treat as unknown (-1)
        if merchant_id == -1:
            merchant_id = self.NR_MXS_train   # last merchant index
        if user_id == -1:
            user_id = self.NR_USERS_train     # last user index

        # ==================
        # Local node indexing
        # ==================
        USER_NODE = 0
        MERCHANT_NODE = 1
        TX_NODE = 2

        # ==================
        # Build edges
        # ==================
        edges_df = pd.DataFrame({
            "src": [USER_NODE, TX_NODE, TX_NODE, MERCHANT_NODE],
            "dst": [TX_NODE, MERCHANT_NODE, USER_NODE, TX_NODE]
        })

        # ==================
        # Build features
        # ==================

        # Transaction features
        tx_feat = self.transformer.transform(df[self.predictor_columns]).astype(np.float32)
        tx_feat_df = pd.DataFrame(
            tx_feat, 
            columns=[c.split("__")[1] for c in self.transformer.get_feature_names_out(self.predictor_columns)]
        )

        # Merchant/user features
        id_input = pd.DataFrame([{
            "Merchant": merchant,
            "Card": card,
            "MCC": df.loc[0, "MCC"]
        }])

        id_features = self.id_transformer.transform(id_input[self.merchant_and_user_cols]).astype(np.float32)
        id_features_df = pd.DataFrame(
            id_features,
            columns=[c.split("__")[1] for c in self.id_transformer.get_feature_names_out(self.merchant_and_user_cols)]
        )

        # Split features into user/merchant parts exactly as in training
        user_cols = [c for c in id_features_df.columns if c.startswith("Card")]
        merchant_cols = [c for c in id_features_df.columns if c not in user_cols]

        user_feat = id_features_df[user_cols].values  # shape (1, d1)
        merchant_feat = id_features_df[merchant_cols].values  # shape (1, d2)
        tx_feat = tx_feat_df.values  # shape (1, d3)

        # ==================
        # Block diagonal node feature matrix
        # ==================
        node_feature_matrix = block_diag(user_feat, merchant_feat, tx_feat)
        

        combined_cols = list(user_cols) + list(merchant_cols) + list(tx_feat_df.columns)
        node_feature_df = pd.DataFrame(node_feature_matrix, columns=combined_cols)

        # ==================
        # Node label (transaction fraud)
        # ==================
        node_label = np.zeros(3, dtype=int)
        if "Is Fraud?" in r:
            node_label[TX_NODE] = 1 if r["Is Fraud?"] == "Yes" else 0

        node_label_df = pd.DataFrame(node_label, columns=["Fraud"])

        # ==================
        # Optional write
        # ==================

        return edges_df, node_feature_df, node_label_df

    def predict_single_transaction(
        self,
        raw_transaction: Dict,
        compute_shap: bool = False,
        decision_threshold: float = 0.5
    ) -> Dict: 

        record_dict = raw_transaction
        # compute feature mask
        features = list(raw_transaction.keys())
        mask_mapping = {}
        feature_mask = []
        current_group_id = 0
        prv_label = ""
        for f in features:
            label = f.split("_")[0]
            
            # print(label, prv_label)
            if label!=prv_label:
                current_group_id+=1
            feature_mask.append(current_group_id)
            mask_mapping[label]=current_group_id
            prv_label = label
        
        # print("Record dict:", record_dict)
        edges, nodes, labels = self.convert_single(record_dict)
        edge_index = edges.values.T.astype(np.int64)
        node_features = nodes.to_numpy()
        compute_shap = np.array([compute_shap], dtype=bool)
    
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
        compute_shap_flag.set_data_from_numpy(np.array([compute_shap], dtype=bool))

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

        # Step 5: Extract results
        prediction = response.as_numpy('PREDICTION')
        y_pred = (prediction > decision_threshold).astype('int8')
        if compute_shap:
            shap_values = response.as_numpy('SHAP_VALUES')
            # print("SHAP values shape:", shap_values.shape)
            feature_to_attribution_map = dict(zip(feature_mask, shap_values[2]))
            feature_name_to_id_map = {v:k for k, v in mask_mapping.items()}
            shap_to_features = {feature_name_to_id_map[k]: f"{v:.3f}" for k, v in feature_to_attribution_map.items()}

        # return (prediction[-1, 0], y_pred[-1, 0])
        result = {
            'fraud_probability': prediction[-1, 0],
            'is_fraud': y_pred[-1, 0],
            'decision_threshold': decision_threshold,
            'shap_values': shap_to_features if compute_shap else None,
        }
        return result

# Example usage
if __name__ == "__main__":
    HOST = "0.0.0.0"
    HTTP_PORT = 8005

    TABFORMER_BASE = os.path.abspath('data/TabFormer/') 
    # same base used in preprocess
    TRANSFORMER_DIR = os.path.join(TABFORMER_BASE, "transformers")
    # Initialize inference client
    inference_client = SingleTransactionInference(
        TRANSFORMER_DIR=TRANSFORMER_DIR,
        host=HOST,
        http_port=HTTP_PORT
    )

    # Example raw transaction
    raw_transaction = {'User': 0, 'Card': 0, 'Year': 2019, 'Month': 1, 'Day': 9, 'Time': '10:18', 'Amount': '$59.17', 'Use Chip': 'Chip Transaction', 'Merchant Name': -4693979874497918566, 'Merchant City': 'North Grafton', 'Merchant State': 'MA', 'Zip': 1536.0, 'MCC': 7538, 'Errors?': 'XX', 'Is Fraud?': 'No', 'Fraud': 0}
    # Predict
    result = inference_client.predict_single_transaction(
        raw_transaction, compute_shap=True
    )

    print(f"Fraud Probability: {result['fraud_probability']:.4f}")
    print(f"Is Fraud: {result['is_fraud']}")