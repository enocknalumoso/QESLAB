"""
QES Stream Controller — Production
Persistent toggles for streams.
"""
import sqlite3
from pathlib import Path
from loguru import logger
from configs.settings import settings


class StreamController:
    """Manages enabled/disabled state for each signal stream."""

    def __init__(self):
        self.db_path = Path(settings.MEMORY_DB_PATH).parent / "stream_state.db"
        self._init_db()
        logger.info("StreamController init")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stream_state (
                    stream TEXT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT 1,
                    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Insert defaults if missing
            defaults = [
                ("FOREX", settings.STREAM_FOREX_ENABLED),
                ("BINARY", settings.STREAM_BINARY_ENABLED),
                ("DAY", settings.STREAM_DAY_ENABLED),
                ("SWING", settings.STREAM_SWING_ENABLED),
                ("BINARY_5M", settings.STREAM_BINARY_5M_ENABLED),
                ("BINARY_10M", settings.STREAM_BINARY_10M_ENABLED),
            ]
            for stream, enabled in defaults:
                conn.execute("""
                    INSERT OR IGNORE INTO stream_state (stream, enabled)
                    VALUES (?, ?)
                """, (stream, enabled))

    def is_enabled(self, stream: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT enabled FROM stream_state WHERE stream = ?",
                (stream,)
            )
            row = cur.fetchone()
            return bool(row[0]) if row else False

    def set_enabled(self, stream: str, enabled: bool):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE stream_state
                SET enabled = ?, last_update = CURRENT_TIMESTAMP
                WHERE stream = ?
            """, (enabled, stream))
        logger.info(f"Stream {stream} → {'ON' if enabled else 'OFF'}")

    def toggle(self, stream: str):
        current = self.is_enabled(stream)
        self.set_enabled(stream, not current)

    @property
    def forex_enabled(self) -> bool:
        return self.is_enabled("FOREX")

    @property
    def binary_enabled(self) -> bool:
        return self.is_enabled("BINARY")

    @property
    def day_enabled(self) -> bool:
        return self.is_enabled("DAY")

    @property
    def swing_enabled(self) -> bool:
        return self.is_enabled("SWING")

    @property
    def binary_5m_enabled(self) -> bool:
        return self.is_enabled("BINARY_5M")

    @property
    def binary_10m_enabled(self) -> bool:
        return self.is_enabled("BINARY_10M")


stream_controller = StreamController()
