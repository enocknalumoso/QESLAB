import sqlite3
from pathlib import Path

def init_db(path, schema):
    with sqlite3.connect(path) as conn:
        conn.executescript(schema)

# Memory DB Schemas
schemas = {
    "/root/qeslab/memory/mistake_memory.db": """
        CREATE TABLE IF NOT EXISTS mistakes (
            id INTEGER PRIMARY KEY,
            strategy_id TEXT,
            reason TEXT,
            market_state BLOB,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "/root/qeslab/memory/success_dna.db": """
        CREATE TABLE IF NOT EXISTS dna (
            id INTEGER PRIMARY KEY,
            attribute TEXT,
            weight REAL,
            strategy_type TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "/root/qeslab/memory/market_conditions.db": """
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            regime TEXT,
            volatility REAL,
            spreads BLOB
        );
    """,
    "/root/qeslab/memory/execution_quality.db": """
        CREATE TABLE IF NOT EXISTS execution (
            id INTEGER PRIMARY KEY,
            signal_id TEXT,
            stream TEXT,
            requested_price REAL,
            executed_price REAL,
            slippage REAL,
            latency_ms INTEGER,
            feedback TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "/root/qeslab/memory/regime_log.db": """
        CREATE TABLE IF NOT EXISTS regimes (
            id INTEGER PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            pair TEXT,
            timeframe TEXT,
            regime_type TEXT,
            confidence REAL
        );
    """,
    "/root/qeslab/memory/knowledge_graph.db": """
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY,
            entity TEXT,
            relationship TEXT,
            target TEXT,
            strength REAL
        );
    """,
    "/root/qeslab/vault/strategies.db": """
        CREATE TABLE IF NOT EXISTS strategies (
            strategy_id TEXT PRIMARY KEY,
            stream TEXT,
            dna_json TEXT,
            performance_json TEXT,
            status TEXT,
            last_audited DATETIME
        );
    """
}

for db_path, schema in schemas.items():
    init_db(db_path, schema)
    print(f"Initialized: {db_path}")

if __name__ == "__main__":
    pass
