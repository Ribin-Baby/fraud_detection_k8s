# run_pipeline.py

import mrc
from mrc.core import operators as ops
import pandas as pd
import os

# Import the new generator and the processor
from synthetic_data_generator import SyntheticDataGenerator
from morpheus_processor import MorpheusProcessor
from morpheus.stages.inference.triton_inference_stage import TritonInferenceStage

# --- Configuration ---
# Set the path to your CSV file with sample data
SOURCE_CSV_FILE = os.path.abspath('data/your_transactions.csv') # <--- IMPORTANT: UPDATE THIS PATH

def create_pipeline(processor: MorpheusProcessor, callback_to_send_to_frontend):
    """
    Builds and returns the full Morpheus pipeline using a synthetic data generator.
    """
    # 1. SOURCE STAGE: Initialize the generator and create the source node
    # This replaces the old static mock_df
    try:
        data_generator = SyntheticDataGenerator(csv_file_path=SOURCE_CSV_FILE)
        # Get the generator object that will be used by the pipeline
        transaction_stream = data_generator.generate_transactions(rate_per_second=2.0)
    except FileNotFoundError:
        print("Could not start pipeline because the source CSV file was not found.")
        # Return an empty pipeline or handle the error appropriately
        return mrc.Pipeline()


    pipeline = mrc.Pipeline()

    # The source node takes the generator directly
    source = pipeline.make_source("synthetic_source", transaction_stream)

    # 2. GRAPH CONVERSION STAGE: (This remains unchanged)
    graph_conversion = pipeline.make_node("graph_conversion", ops.map(processor.convert_to_graph))

    # 3. TRITON INFERENCE STAGE: (This remains unchanged)
    triton_inference = pipeline.make_stage(
        "triton_inference",
        TritonInferenceStage,
        model_name="prediction_and_shapley",
        server_url="localhost:8001",
        force_convert_inputs=True,
        output_mapping={"PREDICTION": "fraud_prediction"}
    )
    
    # 4. SINK STAGE: (This remains unchanged)
    def format_and_send(message):
        original_record = message["original_record"]
        prediction = message["fraud_prediction"]
        
        decision_threshold = 0.5
        fraud_probability = prediction[-1, 0]
        is_fraud = fraud_probability > decision_threshold
        
        ui_payload = {
            "transaction": {k: str(v) for k, v in original_record.items()}, # Ensure values are JSON serializable
            "is_fraud": bool(is_fraud),
            "fraud_score": float(fraud_probability)
        }
        
        callback_to_send_to_frontend(ui_payload)
        return message

    frontend_sink = pipeline.make_node("frontend_sink", ops.map(format_and_send))

    # Connect the pipeline stages (This remains unchanged)
    pipeline.add_edge(source, graph_conversion)
    pipeline.add_edge(graph_conversion, triton_inference)
    pipeline.add_edge(triton_inference, frontend_sink)

    return pipeline

def run_pipeline():
    """
    Initializes and runs the Morpheus pipeline.
    """

    def send_to_frontend_callback(data):
        # This function would send data to the frontend
        print("Sending data to frontend:", data)

    processor = MorpheusProcessor()
    print("Pipeline is running.")
    executor = mrc.Executor()
    # Pass the already initialized processor to the pipeline
    pipeline = create_pipeline(processor, send_to_frontend_callback)
    executor.register_pipeline(pipeline)
    print("Starting Morpheus pipeline in background thread...")
    executor.start()
    executor.join()
    print("Morpheus pipeline has finished.")

if __name__ == "__main__":
    run_pipeline()
    