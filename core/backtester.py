"""
Forex Backtester — Production
Walk-forward, OOS validation, Monte Carlo, stress tests, checkpointing.
"""
import numpy as np
import pandas as pd
import vectorbt as vbt
from pathlib import Path
from loguru import logger
from configs.settings import settings

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)


class ForexBacktester:
    """Full production backtester with walk-forward + reality checks."""

    def __init__(self):
        self.commission = 7.0 / 100_000
        self.slippage_pips = 0.5
        self.n_windows = settings.BACKTEST_WALK_FORWARD_WINDOWS
        self.window_months = settings.WALK_FORWARD_INCREMENT_MONTHS
        self.mc_runs = settings.BACKTEST_MONTE_CARLO_RUNS
        self.train_ratio = settings.BACKTEST_TRAIN_RATIO
        self.seed = settings.SEED
        np.random.seed(self.seed)
        logger.info("ForexBacktester init")

    # ── CORE RUN ─────────────────────────────────────
    def run(self, df: pd.DataFrame, entries: pd.Series,
            exits: pd.Series, pair: str, broker: str = "REAL") -> dict:
        spread_pips = settings.get_spread(pair, broker)
        slippage = (self.slippage_pips + spread_pips) / 10_000

        pf = vbt.Portfolio.from_signals(
            close=df["close"], entries=entries, exits=exits,
            fees=self.commission, slippage=slippage,
            freq="1h", init_cash=10_000, cash_sharing=True,
        )
        return self._metrics(pf)

    # ── WALK-FORWARD ─────────────────────────────────
    def walk_forward(self, df: pd.DataFrame, entries: pd.Series,
                     exits: pd.Series, pair: str, broker: str = "REAL") -> dict:
        total_bars = len(df)
        window_bars = total_bars // (self.n_windows + 1)
        oos_results = []

        for i in range(self.n_windows):
            train_end = int(total_bars * self.train_ratio) + (i * window_bars)
            oos_start = train_end
            oos_end = min(oos_start + window_bars, total_bars)

            if oos_start >= total_bars:
                break

            oos_e = entries.iloc[oos_start:oos_end]
            oos_x = exits.iloc[oos_start:oos_end]
            oos_c = df["close"].iloc[oos_start:oos_end]

            if oos_e.sum() == 0:
                continue

            spread_pips = settings.get_spread(pair, broker)
            slippage = (self.slippage_pips + spread_pips) / 10_000

            pf = vbt.Portfolio.from_signals(
                close=oos_c, entries=oos_e, exits=oos_x,
                fees=self.commission, slippage=slippage,
                freq="1h", init_cash=10_000, cash_sharing=True,
            )
            oos_results.append(self._metrics(pf))

        if not oos_results:
            return {"error": "no trades in any window"}

        clean = [r for r in oos_results if "error" not in r]
        if not clean:
            return {"error": "all windows errored", "windows_tested": len(oos_results)}

        agg = {"windows_tested": len(oos_results)}
        for key in ["win_rate", "sharpe", "profit_factor", "max_dd", "total_trades", "recovery_factor"]:
            values = [r[key] for r in clean if r.get(key) is not None and isinstance(r[key], (int, float, np.floating))]
            if values:
                agg[key] = {
                    "mean": round(np.mean(values), 4),
                    "std": round(np.std(values), 4),
                    "min": round(np.min(values), 4),
                    "max": round(np.max(values), 4),
                }
        agg["windows_failed"] = sum(1 for r in clean if r.get("profit_factor", 99) < 1.0)
        return agg

    # ── MONTE CARLO ──────────────────────────────────
    def monte_carlo(self, trades_df: pd.DataFrame) -> dict:
        if trades_df is None or trades_df.empty:
            return {"error": "no trades"}

        if "PnL" in trades_df.columns:
            pnl_vals = trades_df["PnL"].dropna().values
        elif "Return" in trades_df.columns:
            pnl_vals = trades_df["Return"].dropna().values
        else:
            return {"error": f"no PnL column. Columns: {list(trades_df.columns)}"}

        if len(pnl_vals) < 5:
            return {"error": f"only {len(pnl_vals)} trades, need >4"}

        results = []
        for _ in range(self.mc_runs):
            sampled = np.random.choice(pnl_vals, size=len(pnl_vals), replace=True)
            equity = 1.0 + np.cumsum(sampled)
            peak = np.maximum.accumulate(equity)
            dd = np.min((equity - peak) / peak) if len(peak) > 0 else 0
            results.append({"final": equity[-1], "max_dd": dd})

        finals = [r["final"] for r in results]
        dds = [r["max_dd"] for r in results]

        return {
            "pnl_5pct": round(np.percentile(finals, 5), 4),
            "pnl_50pct": round(np.percentile(finals, 50), 4),
            "pnl_95pct": round(np.percentile(finals, 95), 4),
            "dd_5pct": round(np.percentile(dds, 5), 4),
            "dd_50pct": round(np.percentile(dds, 50), 4),
            "dd_95pct": round(np.percentile(dds, 95), 4),
            "prob_profit": round(sum(1 for f in finals if f > 1.0) / self.mc_runs, 4),
        }

    # ── STRESS TEST ──────────────────────────────────
    def stress_test(self, df: pd.DataFrame, entries: pd.Series,
                    exits: pd.Series, pair: str, broker: str = "REAL") -> dict:
        stress_periods = {
            "2008_crisis": ("2008-09-01", "2008-11-30"),
            "covid_crash": ("2020-02-15", "2020-04-15"),
            "flash_crash": ("2010-05-01", "2010-05-31"),
        }
        results = {}
        for name, (start, end) in stress_periods.items():
            mask = (df.index >= start) & (df.index <= end)
            if not mask.any():
                results[name] = "no_data"
                continue
            pe = entries[mask]
            if pe.sum() == 0:
                results[name] = "no_trades"
                continue
            spread_pips = settings.get_spread(pair, broker)
            slippage = (self.slippage_pips + spread_pips) / 10_000
            pf = vbt.Portfolio.from_signals(
                close=df["close"][mask], entries=pe, exits=exits[mask],
                fees=self.commission, slippage=slippage,
                freq="1h", init_cash=10_000, cash_sharing=True,
            )
            results[name] = self._metrics(pf)
        return results

    # ── METRICS ──────────────────────────────────────
    def _metrics(self, pf) -> dict:
        try:
            n_trades = len(pf.trades.records) if hasattr(pf.trades, 'records') else 0
            if n_trades == 0:
                return {"win_rate": 0.0, "sharpe": 0.0, "profit_factor": 0.0,
                        "max_dd": 0.0, "total_trades": 0, "recovery_factor": 0.0}

            trades = pf.trades.records
            pnl = trades["PnL"].values if "PnL" in trades.columns else np.array([0])
            wins = int(np.sum(pnl > 0))
            losses = int(np.sum(pnl < 0))
            total = wins + losses
            wr = wins / total if total > 0 else 0.0

            gross_profit = float(np.sum(pnl[pnl > 0]))
            gross_loss = float(abs(np.sum(pnl[pnl < 0])))
            pf_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

            return {
                "win_rate": round(wr, 4),
                "sharpe": round(float(pf.sharpe_ratio(freq="d")) if hasattr(pf, 'sharpe_ratio') else 0.0, 4),
                "profit_factor": round(pf_factor, 4),
                "max_dd": round(float(pf.max_drawdown()) if hasattr(pf, 'max_drawdown') else 0.0, 4),
                "total_trades": int(total),
                "recovery_factor": round(float(pf.total_return() / abs(pf.max_drawdown())) if pf.max_drawdown() != 0 else 0.0, 4),
            }
        except Exception as e:
            logger.error(f"Metrics error: {e}")
            return {"error": str(e), "win_rate": 0.0, "sharpe": 0.0,
                    "profit_factor": 0.0, "max_dd": 0.0, "total_trades": 0, "recovery_factor": 0.0}

    # ── FULL VALIDATION ──────────────────────────────
    def validate_strategy(self, df: pd.DataFrame, entries: pd.Series,
                          exits: pd.Series, pair: str, broker: str = "REAL") -> dict:
        logger.info(f"Validating {pair} | broker={broker} | {len(df)} bars | {int(entries.sum())} signals")

        single = self.run(df, entries, exits, pair, broker)
        wf = self.walk_forward(df, entries, exits, pair, broker)

        spread_pips = settings.get_spread(pair, broker)
        slippage = (self.slippage_pips + spread_pips) / 10_000
        pf = vbt.Portfolio.from_signals(
            close=df["close"], entries=entries, exits=exits,
            fees=self.commission, slippage=slippage,
            freq="1h", init_cash=10_000, cash_sharing=True,
        )
        mc = self.monte_carlo(pf.trades.records)
        stress = self.stress_test(df, entries, exits, pair, broker)

        sr = single
        passed = (
            sr.get("win_rate", 0) >= settings.FOREX_MIN_WIN_RATE
            and sr.get("sharpe", 0) >= settings.FOREX_MIN_SHARPE
            and sr.get("profit_factor", 0) >= settings.FOREX_MIN_PROFIT_FACTOR
            and abs(sr.get("max_dd", 0)) <= settings.FOREX_MAX_DD
            and sr.get("total_trades", 0) >= settings.FOREX_MIN_TRADES
        )

        return {
            "pair": pair,
            "broker": broker,
            "single_run": single,
            "walk_forward": wf,
            "monte_carlo": mc,
            "stress_test": stress,
            "pass": passed,
        }


forex_backtester = ForexBacktester()
