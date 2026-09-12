"""
QES Risk Engine — Production
Kelly 25%, ATR sizing, heat limits, pre-signal gates.
"""
import numpy as np
import pandas as pd
from loguru import logger
from configs.settings import settings


class RiskEngine:
    """Full risk engine: sizing, heat limits, pre-signal checks."""

    def __init__(self):
        self.kelly_fraction = settings.KELLY_FRACTION
        self.max_trade_risk = settings.MAX_RISK_PER_TRADE
        self.forex_heat_limit = settings.MAX_PORTFOLIO_HEAT_FOREX
        self.binary_heat_limit = settings.MAX_PORTFOLIO_HEAT_BINARY
        logger.info("RiskEngine init")

    # ── FOREX LOT SIZE ─────────────────────────────────
    def calculate_forex_lot(self, balance: float, sl_pips: float,
                            pair: str = "EURUSD", wr: float = 0.55) -> float:
        """
        Kelly-adjusted lot size: Kelly 25%, max risk 2%.
        pip_value = 10 for majors, 8 for JPY pairs.
        """
        if sl_pips <= 0 or wr < 0.5:
            return 0.0

        # Kelly fraction (25%)
        kelly_bet = wr - (1 - wr) / (1 / wr)
        fraction_bet = kelly_bet * self.kelly_fraction
        fraction_amount = balance * fraction_bet

        # Max risk cap: 2%
        max_risk_amount = balance * self.max_trade_risk
        risk_amount = min(fraction_amount, max_risk_amount)

        # Pip value
        pip_value = 8 if "JPY" in pair else 10
        lots = risk_amount / (sl_pips * pip_value)

        # Minimum lot 0.01
        if lots < 0.01:
            return 0.01

        return round(lots, 2)

    # ── BINARY STAKE ───────────────────────────────────
    def calculate_binary_stake(self, balance: float, wr: float = 0.62) -> float:
        """Kelly 25% on binary, capped at 2%."""
        if wr < settings.BINARY_BREAKEVEN_WR:
            return 0.0

        # Binary Kelly (89% payout, BE WR=52.9%)
        p = wr
        b = settings.BINARY_PAYOUT - 1.0
        kelly = (wr * settings.BINARY_PAYOUT - (1 - wr)) / settings.BINARY_PAYOUT
        fraction_bet = kelly * self.kelly_fraction

        fraction_amount = balance * fraction_bet
        max_risk_amount = balance * self.max_trade_risk
        stake = min(fraction_amount, max_risk_amount)

        return round(stake, 2)

    # ── HEAT CALCULATION ───────────────────────────────
    def calculate_heat(self, positions: list[dict], stream_type: str) -> float:
        """
        Portfolio heat = sum(position risk%) / limit.
        Forex positions: {pair, risk%}. Binary positions: {risk%}.
        """
        total_risk = sum(p["risk_pct"] for p in positions)
        limit = self.forex_heat_limit if stream_type == "FOREX" else self.binary_heat_limit
        return round(total_risk / limit, 2)

    # ── NEWS BLACKOUT ───────────────────────────────────
    def _news_blackout_check(self, current_time: pd.Timestamp) -> bool:
        """
        Placeholder — real data from ForexFactory scraper.
        Returns True if we're inside a news blackout window.
        """
        # TODO: Integrate with core/news_scraper.py
        # For now, mock: block 08:30-08:45 UTC on days with CPI
        hour = current_time.hour
        minute = current_time.minute
        if hour == 8 and 30 <= minute <= 45:
            return True
        return False

    # ── PRE-SIGNAL CHECK ───────────────────────────────
    def pre_signal_check(self, stream_state: dict, signal_type: str,
                         current_time: pd.Timestamp = None) -> dict:
        """
        Full pre-signal gate. Requires current_time (UTC) for news check.
        """
        stream = stream_state["stream"]
        daily_dd = stream_state["daily_dd"]
        total_dd = stream_state["total_dd"]
        heat = stream_state["heat"]
        open_trades = stream_state["open_trades"]

        # Daily DD circuit breaker
        forex_limit = settings.FOREX_DAILY_LOSS_HALT
        binary_limit = settings.BINARY_DAILY_LOSS_HALT
        daily_limit = forex_limit if signal_type == "FOREX" else binary_limit
        if daily_dd >= daily_limit:
            return {"pass": False, "reason": "daily_dd_breached", "limit": daily_limit}

        # Weekly DD
        weekly_limit = settings.FOREX_WEEKLY_CIRCUIT_BREAKER if signal_type == "FOREX" else binary_limit
        if total_dd >= weekly_limit:
            return {"pass": False, "reason": "weekly_dd_breached", "limit": weekly_limit}

        # Heat
        heat_limit = self.forex_heat_limit if signal_type == "FOREX" else self.binary_heat_limit
        if heat >= heat_limit:
            return {"pass": False, "reason": "heat_limit_breached", "limit": heat_limit}

        # Open trades
        max_open = 6 if signal_type == "FOREX" else 10
        if open_trades >= max_open:
            return {"pass": False, "reason": "max_open_trades", "limit": max_open}

        # News blackout (only if current_time provided)
        if current_time is not None:
            blackout = self._news_blackout_check(current_time)
            if blackout:
                return {"pass": False, "reason": "news_blackout"}

        return {"pass": True, "reason": "ok"}

    # ── SINGLE TRADE RISK ──────────────────────────────
    def check_single_trade_risk(self, risk_pct: float) -> bool:
        """Return True if risk% <= 2%."""
        return risk_pct <= self.max_trade_risk

    # ── CORRELATION PENALTY ────────────────────────────
    def correlation_penalty(self, positions: list[dict], new_pair: str,
                            correlation_matrix: pd.DataFrame) -> float:
        """
        Reduce risk% if new pair correlated >70% with existing positions.
        """
        penalty = 1.0
        for pos in positions:
            corr = correlation_matrix.loc[new_pair, pos["pair"]]
            if abs(corr) > 0.70:
                penalty *= 0.5  # Cut risk by half per correlated position
        return penalty


risk_engine = RiskEngine()
