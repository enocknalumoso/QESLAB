"""
QES Binary Backtester — Production
Fixed-expiry only, EV-gated, Monte Carlo, walk-forward.
"""
import numpy as np
import pandas as pd
from pathlib import Path
from loguru import logger
from configs.settings import settings


class BinaryBacktester:
    """Binary options backtester with reality bias checks."""

    def __init__(self):
        self.payout = settings.BINARY_PAYOUT
        self.min_ev = settings.BINARY_MIN_EV
        self.mc_runs = settings.BINARY_MONTE_CARLO_RUNS
        self.seed = settings.SEED
        np.random.seed(self.seed)
        logger.info(f"BinaryBacktester init | payout={self.payout} | min_ev={self.min_ev}")

    # ── CORE RUN ─────────────────────────────────────
    def run(self, df: pd.DataFrame, signals: pd.Series,
            expiry_bars: int) -> dict:
        """
        signals: 1 = CALL, -1 = PUT, 0 = no trade
        expiry_bars: number of bars to expiry
        """
        if signals.abs().sum() == 0:
            return {"win_rate": 0, "ev": 0, "total_trades": 0,
                    "consecutive_losses": 0, "pass": False}

        close = df["close"].values
        signals_arr = signals.values
        total_bars = len(close)
        results = []
        consec_losses = 0
        max_consec = 0

        for i in range(total_bars - expiry_bars):
            sig = signals_arr[i]
            if sig == 0:
                continue

            entry = close[i]
            exit_price = close[i + expiry_bars]

            if sig == 1:  # CALL
                win = 1 if exit_price > entry else 0
            else:  # PUT
                win = 1 if exit_price < entry else 0

            results.append(win)

            if win:
                consec_losses = 0
            else:
                consec_losses += 1
                max_consec = max(max_consec, consec_losses)

        total_trades = len(results)
        wins = sum(results)
        wr = wins / total_trades if total_trades > 0 else 0
        ev = (wr * self.payout) - ((1 - wr) * 1.0)

        # P&L per trade for MC
        pnl = [self.payout if w else -1.0 for w in results]

        return {
            "win_rate": round(wr, 4),
            "ev": round(ev, 4),
            "total_trades": total_trades,
            "wins": wins,
            "consecutive_losses": max_consec,
            "pnl_series": pnl,
            "pass": self._check_pass(wr, ev, total_trades, max_consec),
        }

    # ── PASS CHECK ───────────────────────────────────
    def _check_pass(self, wr: float, ev: float, trades: int,
                    consec_losses: int) -> bool:
        return (
            wr >= settings.BINARY_5M_MIN_WIN_RATE
            and ev >= self.min_ev
            and trades >= settings.BINARY_MIN_TRADES
            and consec_losses <= settings.BINARY_MAX_CONSECUTIVE_LOSSES
        )

    # ── WALK-FORWARD ─────────────────────────────────
    def walk_forward(self, df: pd.DataFrame, signals: pd.Series,
                     expiry_bars: int) -> dict:
        """Walk-forward validation with OOS windows."""
        total_bars = len(df)
        n_windows = settings.BACKTEST_WALK_FORWARD_WINDOWS
        window_bars = total_bars // (n_windows + 1)
        results = []

        for i in range(n_windows):
            train_end = int(total_bars * settings.BACKTEST_TRAIN_RATIO) + (i * window_bars)
            oos_start = train_end
            oos_end = min(oos_start + window_bars, total_bars - expiry_bars)

            if oos_start >= total_bars - expiry_bars:
                break

            oos_df = df.iloc[oos_start:oos_end].reset_index(drop=True)
            oos_signals = signals.iloc[oos_start:oos_end].reset_index(drop=True)

            if oos_signals.abs().sum() == 0:
                continue

            r = self.run(oos_df, oos_signals, expiry_bars)
            results.append({k: v for k, v in r.items() if k != "pnl_series"})

        if not results:
            return {"error": "no trades in any window"}

        agg = {}
        for key in ["win_rate", "ev", "total_trades", "consecutive_losses"]:
            values = [r[key] for r in results if key in r]
            if values:
                agg[key] = {
                    "mean": round(np.mean(values), 4),
                    "std": round(np.std(values), 4),
                    "min": round(np.min(values), 4),
                    "max": round(np.max(values), 4),
                }

        agg["windows_tested"] = len(results)
        agg["windows_passed"] = sum(1 for r in results if r.get("pass", False))
        return agg

    # ── MONTE CARLO ──────────────────────────────────
    def monte_carlo(self, pnl_series: list) -> dict:
        """Monte Carlo on individual trade P&L."""
        if len(pnl_series) < 10:
            return {"error": f"only {len(pnl_series)} trades"}

        pnl = np.array(pnl_series)
        results = []
        for _ in range(self.mc_runs):
            sampled = np.random.choice(pnl, size=len(pnl), replace=True)
            equity = 1.0 + np.cumsum(sampled)
            results.append({
                "final_pnl": equity[-1] - 1.0,
                "max_dd": float(np.min(equity) - 1.0 if np.min(equity) < 1.0 else 0),
            })

        final = [r["final_pnl"] for r in results]
        dd = [r["max_dd"] for r in results]

        return {
            "pnl_5pct": round(np.percentile(final, 5), 4),
            "pnl_50pct": round(np.percentile(final, 50), 4),
            "pnl_95pct": round(np.percentile(final, 95), 4),
            "dd_5pct": round(np.percentile(dd, 5), 4),
            "dd_50pct": round(np.percentile(dd, 50), 4),
            "dd_95pct": round(np.percentile(dd, 95), 4),
            "prob_profit": round(sum(1 for p in final if p > 0) / self.mc_runs, 4),
        }

    # ── FULL VALIDATION ──────────────────────────────
    def validate_strategy(self, df: pd.DataFrame, signals: pd.Series,
                          expiry_bars: int, pair: str = "", tf: str = "") -> dict:
        """Run all tests and return full report."""
        logger.info(f"Binary validate {pair} {tf} | bars={len(df)} | signals={int(signals.abs().sum())}")

        single = self.run(df, signals, expiry_bars)
        wf = self.walk_forward(df, signals, expiry_bars)
        mc = self.monte_carlo(single.get("pnl_series", []))

        return {
            "pair": pair,
            "timeframe": tf,
            "expiry_bars": expiry_bars,
            "single_run": {k: v for k, v in single.items() if k != "pnl_series"},
            "walk_forward": wf,
            "monte_carlo": mc,
            "pass": single["pass"],
        }


binary_backtester = BinaryBacktester()
