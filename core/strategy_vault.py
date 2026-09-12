import sqlite3
import json
from datetime import datetime
from configs.settings import settings

class StrategyVault:
    def __init__(self):
        self.db_path = settings.VAULT_DB_PATH

    def save_strategy(self, strategy_id, stream, dna, performance):
        """Saves a strategy to the vault."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO strategies 
                (strategy_id, stream, dna_json, performance_json, status, last_audited)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                strategy_id, 
                stream, 
                json.dumps(dna), 
                json.dumps(performance), 
                "PENDING", 
                datetime.utcnow()
            ))

    def get_active_strategies(self, stream):
        """Retrieves all strategies currently marked as LIVE."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT strategy_id, dna_json FROM strategies WHERE stream = ? AND status = 'LIVE'", 
                (stream,)
            )
            return [{"id": row[0], "dna": json.loads(row[1])} for row in cursor.fetchall()]

    def update_status(self, strategy_id, status):
        """Updates strategy status (LIVE, RETIRED, FAILED)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE strategies SET status = ?, last_audited = ? WHERE strategy_id = ?",
                (status, datetime.utcnow(), strategy_id)
            )

strategy_vault = StrategyVault()

# Singleton instance for Orchestrator
strategy_vault = StrategyVault()
