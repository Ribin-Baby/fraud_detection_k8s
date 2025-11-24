# morpheus_processor.py

import json
import os
import numpy as np
import pandas as pd
from scipy.linalg import block_diag
import pickle
from typing import Dict

class MorpheusProcessor:
    """
    Handles loading all preprocessing assets and contains the core logic
    for converting a transaction dictionary into a graph format for Triton.
    """
    def __init__(self, transformer_dir: str):
        print("Initializing MorpheusProcessor and loading assets...")
        # Load all necessary transformers and metadata
        with open(os.path.join(transformer_dir, "transformer.pkl"), 'rb') as f:
            self.transformer = pickle.load(f)
        with open(os.path.join(transformer_dir, "id_transformer.pkl"), 'rb') as f:
            self.id_transformer = pickle.load(f)
        with open(os.path.join(transformer_dir, "metadata.pkl"), 'rb') as f:
            self.mappings = pickle.load(f)
        with open(os.path.join(transformer_dir, "metadata.json"), "r") as f:
            self.metadata = json.load(f)
        
        # Extract metadata and column definitions
        self.merchant_name_to_id = self.mappings["merchant_name_to_id"]
        self.id_to_consecutive_id = self.mappings["card_to_user_id"]
        self.NR_USERS_train = self.metadata.get("NR_USERS")
        self.NR_MXS_train = self.metadata.get("NR_MXS")
        self.predictor_columns = self.metadata.get("predictor_columns")
        self.merchant_and_user_cols = self.metadata.get("merchant_and_user_cols")
        print("Assets loaded successfully.")

    def normalize_row(self, row: Dict) -> Dict:
        # (Your normalize_row method, copied directly)
        r = row.copy()
        if isinstance(r.get("Amount"), str) and r["Amount"].startswith("$"):
            r["Amount"] = float(r["Amount"].replace("$", ""))
        if isinstance(r.get("Time"), str):
            hh, mm = r["Time"].split(":")
            r["Time"] = int(hh) * 60 + int(mm)
        if "Is Fraud?" in r:
            r["Fraud"] = 1 if r["Is Fraud?"] == "Yes" else 0
        r['Merchant'] = str(r.get('Merchant Name', 'Unknown'))
        r['Chip'] = r.get('Use Chip', 'Swipe Transaction')
        r['City'] = r.get('Merchant City', 'Unknown')
        r['State'] = r.get('Merchant State', 'XX')
        r['Errors'] = r.get('Errors?', 'XX').replace(',', '')
        return r

    def convert_to_graph(self, record_dict: Dict) -> Dict:
        """
        The core processing function for the Morpheus map stage.
        Takes a single transaction dict and returns a dict of tensors for Triton.
        """
        # (The logic from your convert_single method)
        r = self.normalize_row(record_dict)
        df = pd.DataFrame([r])

        # --- Map IDs ---
        merchant = df.loc[0, "Merchant"]
        card = df.loc[0, "Card"]
        # merchant_id = self.merchant_name_to_id.get(str(merchant), self.NR_MXS_train)
        # user_id = self.id_to_consecutive_id.get(card, self.NR_USERS_train)

        # --- Local node indexing ---
        USER_NODE, MERCHANT_NODE, TX_NODE = 0, 1, 2

        # --- Build edges ---
        edges_df = pd.DataFrame({
            "src": [USER_NODE, TX_NODE, TX_NODE, MERCHANT_NODE],
            "dst": [TX_NODE, MERCHANT_NODE, USER_NODE, TX_NODE]
        })
        edge_index = edges_df.values.T.astype(np.int64)

        # --- Build features ---
        tx_feat = self.transformer.transform(df[self.predictor_columns]).astype(np.float32)
        id_input = pd.DataFrame([{"Merchant": merchant, "Card": card, "MCC": df.loc[0, "MCC"]}])
        id_features = self.id_transformer.transform(id_input[self.merchant_and_user_cols]).astype(np.float32)
        id_features_df = pd.DataFrame(id_features, columns=[c.split("__")[1] for c in self.id_transformer.get_feature_names_out(self.merchant_and_user_cols)])
        
        user_cols = [c for c in id_features_df.columns if c.startswith("Card")]
        merchant_cols = [c for c in id_features_df.columns if c not in user_cols]
        user_feat = id_features_df[user_cols].values
        merchant_feat = id_features_df[merchant_cols].values
        
        node_features = block_diag(user_feat, merchant_feat, tx_feat).astype(np.float32)

        # --- Prepare output for the next stage ---
        # The keys here MUST match the input names of your model in Triton
        return {
            "NODE_FEATURES": node_features,
            "EDGE_INDEX": edge_index,
            "original_record": record_dict  # Pass along for context
        }