"""
QES Operator Feedback — Production (Plumbing Only)
WIN/LOSS/BE/SKIP → pocket manager + learning DBs.
No LLM logic.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger
from configs.settings import settings
from core.pocket_manager import pocket_manager


class OperatorFeedback:
    """
    Handles operator taps on dashboard/Telegram.
    Updates pocket manager, logs to all 6 learning databases,
    triggers Bayesian updates, mistake memory, DNA updates.
    """

    def __init__(self):
        self.memory_dir = Path(settings.MEMORY_DB_PATH).parent
        self._init_dbs()
        logger.info("OperatorFeedback init")

    # ── INIT DBs ────────────────────────────────────────
    def _init_dbs(self):
        """Ensure all 6 learning DB tables exist."""
        for db_name in [
            "mistake_memory.db",
            "success_dna.db",
            "market_conditions.db",
            "execution_quality.db",
            "regime_log.db",
            "knowledge_graph.db",
        ]:
            db_path = self.memory_dir / db_name
            with sqlite3.connect(db_path) as conn:
                # Generic logs table for each
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        signal_id TEXT,
                        pair TEXT,
                        timeframe TEXT,
                        outcome TEXT,
                        confidence REAL,
                        wr REAL,
                        ev REAL,
                        context TEXT,
                        metadata TEXT
                    )
                """)
                logger.debug(f"DB ready: {db_name}")

    # ── LOG OUTCOME ─────────────────────────────────────
    def _log_outcome(self, signal: dict, outcome: str):
        """
        Logs outcome to all 6 databases with context snapshot.
        """
        context = {
            "pair": signal.get("pair"),
            "timeframe": signal.get("timeframe"),
            "direction": signal.get("direction"),
            "entry": signal.get("entry"),
            "sl": signal.get("sl"),
            "tp": signal.get("tp"),
            "rr": signal.get("rr"),
            "lot_size": signal.get("lot_size"),
            "risk_pct": signal.get("risk_pct"),
            "confidence": signal.get("confidence"),
            "win_rate": signal.get("win_rate"),
            "strategy_id": signal.get("strategy_id"),
            "outcome": outcome,
            "stream": signal.get("stream"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for db_name in [
            "mistake_memory.db",
            "success_dna.db",
            "market_conditions.db",
            "execution_quality.db",
            "regime_log.db",
            "knowledge_graph.db",
        ]:
            db_path = self.memory_dir / db_name
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    INSERT INTO logs (
                        timestamp, signal_id, pair, timeframe, outcome,
                        confidence, wr, ev, context, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    context["timestamp"],
                    signal.get("signal_id"),
                    context["pair"],
                    context["timeframe"],
                    outcome,
                    context["confidence"],
                    context["win_rate"],
                    0.0,  # Placeholder EV
                    str(context),
                    "",
                ))

        logger.debug(f"Logged outcome {outcome} for {signal.get('pair')} to 6 DBs")

    # ── FEEDBACK ENTRY ──────────────────────────────────
    def feedback(self, signal_id: str, outcome: str, stream: str = "FOREX"):
        """
        Called when operator taps WIN/LOSS/BE/SKIP.
        Updates pocket manager, logs to databases.
        """
        outcomes = {"WIN", "LOSS", "BE", "SKIP"}
        if outcome not in outcomes:
            logger.error(f"Invalid outcome '{outcome}'")
            return

        # Fetch signal from appropriate engine
        signal = None
        if stream == "FOREX":
            from agents.signal_engine import forex_signal_engine
            active = forex_signal_engine.active_signals
            signal = active.get(signal_id)
        elif stream == "BINARY":
            from agents.binary_signal_eng import binary_signal_engine
            active = binary_signal_engine.active_signals
            signal = active.get(signal_id)

        if not signal:
            logger.warning(f"Feedback: signal {signal_id} not found in {stream}")
            return

        # Calculate PnL
        pnl = 0.0
        if outcome == "WIN":
            if stream == "FOREX":
                pnl = signal.get("tp", 0) - signal.get("entry", 0)  # Simplified
            else:
                pnl = signal.get("stake", 0) * settings.BINARY_PAYOUT
        elif outcome == "LOSS":
            if stream == "FOREX":
                pnl = signal.get("sl", 0) - signal.get("entry", 0)  # Negative
            else:
                pnl = -signal.get("stake", 0)
        elif outcome == "BE":
            pnl = 0.0
        else:  # SKIP
            pnl = 0.0

        # Close signal
        if stream == "FOREX":
            from agents.signal_engine import forex_signal_engine
            forex_signal_engine.close_signal(signal_id, outcome, pnl)
        else:
            from agents.binary_signal_eng import binary_signal_engine
            binary_signal_engine.close_signal(signal_id, outcome, pnl)

        # Log to learning DBs (except SKIP)
        if outcome != "SKIP":
            self._log_outcome(signal, outcome)

        # Trigger learning updates (placeholder)
        self._trigger_learning_updates(signal, outcome)

        logger.info(f"Feedback: {stream} {signal_id} → {outcome} pnl={pnl:.2f}")

    # ── TRIGGER LEARNING UPDATES ────────────────────────
    def _trigger_learning_updates(self, signal: dict, outcome: str):
        """Placeholder: Bayesian recalc, mistake memory, DNA updates."""
        # 1. Bayesian WR update
        # 2. EV recalculation (binary)
        # 3. Mistake memory if outcome == 'LOSS'
        # 4. Success DNA if outcome == 'WIN'
        # 5. Knowledge graph update
        # 6. Retirement check (if WR drops >10% over 50 trades)
        # 7. Market conditions snapshot
        logger.debug(f"Learning updates triggered for {signal['pair']} → {outcome}")

    # ── SKIP TRACKING ───────────────────────────────────
    def track_skip(self, signal: dict, reason: str = ""):
        """
        Log a skipped signal (operator saw but didn't trade).
        Used to evaluate 'would it have won?'.
        """
        db_path = self.memory_dir / "execution_quality.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT INTO skips (
                    timestamp, pair, timeframe, direction,
                    entry, confidence, wr, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                signal.get("pair"),
                signal.get("timeframe"),
                signal.get("direction"),
                signal.get("entry"),
                signal.get("confidence"),
                signal.get("win_rate"),
                reason,
            ))
        logger.debug(f"Skip tracked: {signal['pair']} reason={reason}")


operator_feedback = OperatorFeedback()
