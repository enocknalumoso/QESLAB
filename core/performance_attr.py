import sqlite3
import pandas as pd
from configs.settings import settings

class PerformanceAttributor:
    def __init__(self):
        self.db_path = "/root/qeslab/memory/execution_quality.db"

    def calculate_metrics(self, stream):
        """Calculates live performance stats from operator feedback."""
        with sqlite3.connect(self.db_path) as conn:
            query = f"SELECT feedback FROM execution WHERE stream = '{stream}'"
            df = pd.read_sql(query, conn)
            
            if df.empty:
                return {"wr": 0.0, "total": 0}
            
            wins = len(df[df['feedback'] == 'win'])
            total = len(df[df['feedback'].isin(['win', 'loss'])])
            
            wr = (wins / total) if total > 0 else 0.0
            return {"wr": wr, "total": total}

performance_attr = PerformanceAttributor()
