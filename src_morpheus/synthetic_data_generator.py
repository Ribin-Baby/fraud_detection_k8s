# synthetic_data_generator.py

import pandas as pd
import time
from typing import Iterator, Dict

class SyntheticDataGenerator:
    """
    Loads a source CSV file and generates an infinite stream of synthetic
    transactions by randomly sampling values from each column.
    """
    def __init__(self, csv_file_path: str):
        """
        Initializes the generator by loading the source data.

        Parameters:
        -----------
        csv_file_path : str
            Path to the CSV file containing example transactions.
        """
        print(f"Loading source data from: {csv_file_path}")
        try:
            # Load the entire CSV into memory for efficient sampling
            self.source_df = pd.read_csv(csv_file_path)
            # Drop rows with missing values to ensure clean samples
            self.source_df.dropna(inplace=True)
            self.columns = self.source_df.columns
            print(f"Successfully loaded {len(self.source_df)} rows of sample data.")
        except FileNotFoundError:
            print(f"Error: The file '{csv_file_path}' was not found.")
            raise

    def generate_transactions(self, rate_per_second: float = 2.0) -> Iterator[Dict]:
        """
        A Python generator that yields new, randomly constructed transaction
        dictionaries at a specified rate.

        Parameters:
        -----------
        rate_per_second : float
            The number of transactions to generate per second.
        """
        sleep_interval = 1.0 / rate_per_second
        
        print(f"Starting transaction stream at ~{rate_per_second} transactions/sec...")
        while True:
            new_transaction = {}
            # For each column, pick one random value from the source DataFrame
            for col in self.columns:
                # .sample(1).iloc[0] is an efficient way to get a single random value
                new_transaction[col] = self.source_df[col].sample(1).iloc[0]
            
            yield new_transaction
            
            # Control the streaming speed
            time.sleep(sleep_interval)