import polars as pl
import pandas as pd
from pathlib import Path

class CorrelationMonitor:
    def __init__(self):
        self.threshold = 0.70

    def check_correlation(self, price_data: dict):
        """
        Input: dict of {pair: pd.Series of close prices}
        Output: list of pairs to remove
        """
        if not price_data:
            return []
            
        df = pd.DataFrame(price_data)
        corr_matrix = df.corr().abs()
        
        to_remove = set()
        columns = corr_matrix.columns
        
        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                if corr_matrix.iloc[i, j] > self.threshold:
                    # Keep the one with higher volatility (simplified logic)
                    to_remove.add(columns[j])
                    
        return list(to_remove)

correlation_monitor = CorrelationMonitor()
