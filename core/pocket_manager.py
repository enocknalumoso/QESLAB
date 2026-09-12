"""
QES Pocket Manager — Production
Tracks operator-reported state only, never reads MT5.
SQLite WAL, Telegram alerts, daily briefing, circuit breakers.
"""
import sqlite3
import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from loguru import logger
from configs.settings import settings


class PocketManager:
    """
    State: balance, equity, daily DD, total DD, open positions,
           daily gain, heat, breaker status.
    Daily briefing: 06:00 UTC.
    Telegram alerts at 80% DD limit.
    Halt + 30min cooldown on breach.
    """

    def __init__(self):
        self.db_path = Path(settings.MEMORY_DB_PATH).parent / "pocket_state.db"
        self.poll_interval = settings.PM_POLL_INTERVAL
        self.dd_alert_threshold = settings.PM_DD_ALERT_THRESHOLD
        self.cooldown_minutes = settings.PM_COOLDOWN_MINUTES
        self._init_db()
        logger.info(f"PocketManager init | db={self.db_path}")

    # ── DATABASE ─────────────────────────────────────────
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Enable WAL for concurrency
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS account_state (
                    stream TEXT PRIMARY KEY,
                    balance REAL DEFAULT 10000.0,
                    equity REAL DEFAULT 10000.0,
                    daily_dd REAL DEFAULT 0.0,
                    total_dd REAL DEFAULT 0.0,
                    daily_gain REAL DEFAULT 0.0,
                    open_trades INTEGER DEFAULT 0,
                    heat REAL DEFAULT 0.0,
                    breaker_active BOOLEAN DEFAULT FALSE,
                    breaker_since TIMESTAMP,
                    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_briefing (
                    date TEXT PRIMARY KEY,
                    content TEXT,
                    sent BOOLEAN DEFAULT FALSE
                )
            """)
            # Initialize forex and binary streams
            conn.execute("""
                INSERT OR IGNORE INTO account_state (stream)
                VALUES ('FOREX'), ('BINARY')
            """)

    # ── STATE UPDATES ───────────────────────────────────
    def update_balance(self, stream: str, balance: float, equity: float = None):
        """Operator calls /status [balance] — updates both balance and equity."""
        with sqlite3.connect(self.db_path) as conn:
            eq = equity if equity is not None else balance
            conn.execute("""
                UPDATE account_state
                SET balance = ?, equity = ?, last_update = ?
                WHERE stream = ?
            """, (balance, eq, datetime.now(timezone.utc), stream))
        logger.info(f"Update {stream}: balance={balance}, equity={eq}")

    def update_trade_opened(self, stream: str, risk_pct: float):
        """Called when a new trade is opened."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT heat FROM account_state WHERE stream = ?", (stream,))
            heat = cur.fetchone()[0]
            new_heat = heat + risk_pct
            conn.execute("""
                UPDATE account_state
                SET open_trades = open_trades + 1,
                    heat = ?,
                    last_update = ?
                WHERE stream = ?
            """, (new_heat, datetime.now(timezone.utc), stream))
        logger.info(f"Trade opened {stream}: risk={risk_pct}%, heat={new_heat}")

    def update_trade_closed(self, stream: str, pnl: float, risk_pct: float):
        """Called when a trade closes — updates equity, DD, heat."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                SELECT balance, equity, daily_dd, total_dd, heat, open_trades
                FROM account_state WHERE stream = ?
            """, (stream,))
            bal, eq, daily, total, heat, open_trades = cur.fetchone()
            new_equity = eq + pnl
            new_heat = heat - risk_pct
            # Update DD
            if new_equity < bal:
                loss = bal - new_equity
                daily_loss = max(daily, loss / bal)
                total_loss = max(total, loss / bal)
            else:
                daily_loss = daily
                total_loss = total

            conn.execute("""
                UPDATE account_state
                SET equity = ?,
                    daily_dd = ?,
                    total_dd = ?,
                    heat = ?,
                    open_trades = ?,
                    last_update = ?
                WHERE stream = ?
            """, (new_equity, daily_loss, total_loss, new_heat, open_trades - 1,
                  datetime.now(timezone.utc), stream))

        self._check_circuit_breakers(stream)
        logger.info(f"Trade closed {stream}: pnl={pnl}, new equity={new_equity}")

    # ── CIRCUIT BREAKERS ────────────────────────────────
    def _check_circuit_breakers(self, stream: str):
        """Activate breaker if daily DD exceeds limit."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                SELECT daily_dd, total_dd FROM account_state WHERE stream = ?
            """, (stream,))
            daily, total = cur.fetchone()

            daily_limit = (settings.FOREX_DAILY_LOSS_HALT if stream == "FOREX"
                           else settings.BINARY_DAILY_LOSS_HALT)
            total_limit = (settings.FOREX_WEEKLY_CIRCUIT_BREAKER if stream == "FOREX"
                           else settings.BINARY_DAILY_LOSS_HALT)

            if daily >= daily_limit or total >= total_limit:
                conn.execute("""
                    UPDATE account_state
                    SET breaker_active = TRUE,
                        breaker_since = ?
                    WHERE stream = ?
                """, (datetime.now(timezone.utc), stream))
                logger.warning(f"Circuit breaker activated for {stream} | daily={daily}")

    def reset_daily(self):
        """Called at 00:00 UTC — resets daily DD, gain, open trades."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE account_state
                SET daily_dd = 0.0,
                    daily_gain = 0.0,
                    open_trades = 0,
                    breaker_active = FALSE,
                    breaker_since = NULL
            """)
        logger.info("Daily reset applied")

    # ── GET STATE ───────────────────────────────────────
    def get_state(self, stream: str) -> dict:
        """Returns all state fields."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                SELECT balance, equity, daily_dd, total_dd, open_trades,
                       heat, breaker_active, breaker_since
                FROM account_state WHERE stream = ?
            """, (stream,))
            row = cur.fetchone()
            if not row:
                return {}
            bal, eq, daily, total, opens, heat, breaker, since = row
            return {
                "stream": stream,
                "balance": bal,
                "equity": eq,
                "daily_dd": daily,
                "total_dd": total,
                "open_trades": opens,
                "heat": heat,
                "breaker_active": bool(breaker),
                "breaker_since": since,
                "breaker_remaining": self._remaining_cooldown(since) if breaker else 0,
            }

    def _remaining_cooldown(self, since_str: str) -> int:
        """Minutes left in cooldown."""
        if not since_str:
            return 0
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - since
        remaining = self.cooldown_minutes - (delta.total_seconds() / 60)
        return max(0, int(remaining))

    # ── DAILY BRIEFING ──────────────────────────────────
    def generate_daily_briefing(self) -> str:
        """Formats daily briefing for Telegram/dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM account_state")
            rows = cur.fetchall()

        lines = []
        for row in rows:
            stream, bal, eq, daily, total, gain, opens, heat, breaker, since, _ = row
            lines.append(f"{stream}: balance={bal:.0f} | equity={eq:.0f} | "
                         f"daily DD={daily:.1%} | open={opens}")

        # Mock news — from ForexFactory scraper later
        news_lines = [
            "08:30 USD CPI [HIGH] ⛔±15min",
            "13:30 GBP Employment [HIGH] ⛔±15min",
        ]

        briefing = f"""
━━━━━━━━━━━━━━━━━━━━
📊 QES DAILY BRIEFING
━━━━━━━━━━━━━━━━━━━━
DD Status:
  Forex: {daily:.1%} / {settings.FOREX_DAILY_LOSS_HALT:.1%} daily
  Binary: X.X% / {settings.BINARY_DAILY_LOSS_HALT:.1%} daily

Sessions (UTC):
  London: {settings.SESSION_LONDON_START} | NY: {settings.SESSION_NY_START}
  ⚡ Peak overlap: {settings.OVERLAP_LONDON_NY_START}-{settings.OVERLAP_LONDON_NY_END}

News Today (UTC):
  {chr(10).join(f'  {n}' for n in news_lines)}

Streams:
  Forex Day 🟢 | Swing 🟢
  Binary 5M 🟢 | 10M 🟢
━━━━━━━━━━━━━━━━━━━━
"""
        return briefing

    def save_briefing(self, content: str):
        """Store briefing in DB."""
        today = datetime.now(timezone.utc).date().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_briefing (date, content, sent)
                VALUES (?, ?, FALSE)
            """, (today, content))

    # ── TELEGRAM ALERT ──────────────────────────────────
    def check_alert(self, stream: str) -> str:
        """If DD > 80% limit, returns alert message."""
        state = self.get_state(stream)
        daily = state["daily_dd"]
        limit = (settings.FOREX_DAILY_LOSS_HALT if stream == "FOREX"
                 else settings.BINARY_DAILY_LOSS_HALT)
        if daily >= limit * self.dd_alert_threshold:
            return (f"⚠️ {stream} DD Alert: {daily:.1%} / {limit:.1%} daily\n"
                    f"Balance: {state['balance']:.0f}")
        return ""

    # ── PRE‑SIGNAL GATE ─────────────────────────────────
    def pre_signal_gate(self, stream: str, signal_type: str,
                        current_time: datetime = None) -> dict:
        """
        Called before every signal.
        Returns {pass: bool, reason: str, cooldown_remaining: int}.
        """
        state = self.get_state(stream)

        if state["breaker_active"]:
            remaining = self._remaining_cooldown(state["breaker_since"])
            if remaining > 0:
                return {"pass": False, "reason": "cooldown_active",
                        "cooldown_remaining": remaining}
            else:
                # Cooldown expired, reset breaker
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        UPDATE account_state
                        SET breaker_active = FALSE,
                            breaker_since = NULL
                        WHERE stream = ?
                    """, (stream,))
                logger.info(f"Cooldown expired for {stream}, breaker reset")

        # Use risk engine for full check
        from core.risk_engine import risk_engine
        return risk_engine.pre_signal_check(state, signal_type, current_time)


pocket_manager = PocketManager()
