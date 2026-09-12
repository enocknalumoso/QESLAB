from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="/root/qeslab/.env",
        env_file_encoding="utf-8",
        extra="allow"
    )

    # Paths
    DATA_RAW_PATH: str = "/root/qeslab/data/raw"
    DATA_RESAMPLED_PATH: str = "/root/qeslab/data/resampled"
    MEMORY_DB_PATH: str = "/root/qeslab/memory"
    VAULT_DB_PATH: str = "/root/qeslab/vault/strategies.db"
    MT5_REAL_LOGIN: int = 0
    MT5_REAL_PASSWORD: str = ""
    MT5_REAL_SERVER: str = ""
    MT5_OTC_LOGIN: int = 0
    MT5_OTC_PASSWORD: str = ""
    MT5_OTC_SERVER: str = ""

    # Backtesting
    BACKTEST_TRAIN_RATIO: float = 0.7
    BACKTEST_WALK_FORWARD_WINDOWS: int = 4
    BACKTEST_MONTE_CARLO_RUNS: int = 1000

    # Forex Operational Limits
    FOREX_MIN_WIN_RATE: float = 0.52
    FOREX_MIN_SHARPE: float = 1.2
    FOREX_MIN_PROFIT_FACTOR: float = 1.5
    FOREX_MAX_DD: float = 0.15
    FOREX_MIN_TRADES: int = 30
    FOREX_DAILY_LOSS_HALT: float = 0.05
    FOREX_WEEKLY_CIRCUIT_BREAKER: float = 0.10
    MAX_ALLOWED_SPREAD_FOREX: float = 3.0

    # Binary Operational Limits
    BINARY_PAYOUT: float = 0.89
    BINARY_MIN_EV: float = 0.08

    # REAL (Exness) spread limits
    REAL_MAX_SPREAD_EURUSD: float = 1.5
    REAL_MAX_SPREAD_GBPUSD: float = 1.8
    REAL_MAX_SPREAD_USDJPY: float = 1.8
    REAL_MAX_SPREAD_AUDUSD: float = 1.8
    REAL_MAX_SPREAD_USDCAD: float = 2.5
    REAL_MAX_SPREAD_USDCHF: float = 2.5
    REAL_MAX_SPREAD_EURJPY: float = 2.5
    REAL_MAX_SPREAD_GBPJPY: float = 3.5
    REAL_MAX_SPREAD_AUDJPY: float = 3.0
    REAL_MAX_SPREAD_CADJPY: float = 3.0

    # OTC (PoTrade) spread limits
    OTC_MAX_SPREAD_EURUSD: float = 2.5
    OTC_MAX_SPREAD_GBPUSD: float = 3.0
    OTC_MAX_SPREAD_USDJPY: float = 3.5
    OTC_MAX_SPREAD_AUDUSD: float = 3.0
    OTC_MAX_SPREAD_USDCAD: float = 3.5
    OTC_MAX_SPREAD_USDCHF: float = 3.0
    OTC_MAX_SPREAD_EURJPY: float = 3.5
    OTC_MAX_SPREAD_GBPJPY: float = 5.0
    OTC_MAX_SPREAD_AUDJPY: float = 4.0
    OTC_MAX_SPREAD_CADJPY: float = 5.0

    def get_spread(self, pair: str, broker: str) -> float:
        clean = pair.rstrip("m") if broker.upper() == "REAL" else pair
        attr = f"{broker.upper()}_MAX_SPREAD_{clean}"
        return getattr(self, attr, 1.0)

settings = Settings()
