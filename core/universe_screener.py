"""
QES Universe Screener — Production
5-stage filtering. Auto-detects available pairs from resampled/.
14 pairs → filters to what exists → scores → tiers.
"""
import polars as pl
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from loguru import logger
from configs.settings import settings


class UniverseScreener:
    """Screens available pairs down to deployable tiered candidates."""

    CORE_PAIRS = [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
        "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY", "EURGBP",
    ]

    def __init__(self):
        self.resampled_path = Path(settings.DATA_RESAMPLED_PATH)
        self.correlation_threshold = 0.70
        self.max_candidates = 9
        self.available_pairs = self._detect_pairs()
        logger.info(f"UniverseScreener init | {len(self.available_pairs)} pairs available")

    def _detect_pairs(self) -> list[str]:
        """Find all pairs that have D1 resampled data."""
        files = list(self.resampled_path.glob("*_D1.parquet"))
        pairs = sorted(set(f.stem.replace("_D1", "") for f in files))
        return pairs

    # ── STAGE 1: FAST FILTER ────────────────────────
    def stage1_filter(self, timeframe: str = "D1", lookback_days: int = 90) -> list[dict]:
        """Quick filter on average daily range and volume."""
        candidates = []
        for pair in self.available_pairs:
            fpath = self.resampled_path / f"{pair}_{timeframe}.parquet"
            if not fpath.exists():
                continue

            df = pl.read_parquet(fpath).tail(lookback_days)
            if df.height == 0:
                continue

            avg_range = (df["high"] - df["low"]).mean()
            avg_volume = df["volume"].mean()
            avg_spread = df["avg_spread"].mean() if "avg_spread" in df.columns else 0.0

            candidates.append({
                "pair": pair,
                "avg_range": round(float(avg_range), 6),
                "avg_volume": round(float(avg_volume), 0),
                "avg_spread": round(float(avg_spread), 6),
            })

        candidates = candidates  # volume not used in forex
        logger.info(f"Stage 1: {len(candidates)}/{len(self.available_pairs)} passed fast filter")
        return candidates

    # ── STAGE 2: RANK & SHORTLIST ───────────────────
    def stage2_rank(self, candidates: list[dict]) -> list[dict]:
        """Composite score: range rank + volume rank - spread penalty. Top N."""
        if not candidates:
            return []

        by_range = sorted(candidates, key=lambda x: x["avg_range"], reverse=True)
        for i, c in enumerate(by_range):
            c["range_rank"] = i + 1

        by_vol = sorted(candidates, key=lambda x: x["avg_volume"], reverse=True)
        for i, c in enumerate(by_vol):
            c["volume_rank"] = i + 1

        for c in candidates:
            c["score"] = c["range_rank"] + c["volume_rank"] + (c["avg_spread"] * 10_000)

        ranked = sorted(candidates, key=lambda x: x["score"])[:self.max_candidates]
        logger.info(f"Stage 2: shortlisted {len(ranked)} candidates")
        return ranked

    # ── STAGE 3: CORRELATION FILTER ─────────────────
    def stage3_correlation(self, candidates: list[dict],
                           timeframe: str = "H1",
                           lookback_days: int = 60) -> list[dict]:
        """Remove pairs >70% correlated, keeping higher-ranked."""
        if len(candidates) <= 1:
            return candidates

        pair_names = [c["pair"] for c in candidates]
        returns_data = {}
        valid_pairs = []

        for pair in pair_names:
            fpath = self.resampled_path / f"{pair}_{timeframe}.parquet"
            if not fpath.exists():
                continue
            df = pl.read_parquet(fpath).tail(lookback_days * 24)
            if df.height < 10:
                continue
            returns_data[pair] = df["close"].to_numpy()
            valid_pairs.append(pair)

        if len(valid_pairs) <= 1:
            return [c for c in candidates if c["pair"] in valid_pairs]

        min_len = min(len(v) for v in returns_data.values())
        returns_matrix = np.column_stack([
            np.diff(np.log(v[-min_len:])) for v in returns_data.values()
        ])

        corr = np.corrcoef(returns_matrix.T)
        n = len(valid_pairs)

        removed = set()
        for i in range(n):
            if valid_pairs[i] in removed:
                continue
            for j in range(i + 1, n):
                if valid_pairs[j] in removed:
                    continue
                if abs(corr[i][j]) > self.correlation_threshold:
                    # Remove lower-ranked (higher index in candidates)
                    later = valid_pairs[max(i, j)]
                    removed.add(later)
                    logger.debug(f"Corr {valid_pairs[i]} vs {valid_pairs[j]}: {corr[i][j]:.3f} → removed {later}")

        kept = [c for c in candidates if c["pair"] not in removed]
        logger.info(f"Stage 3: {len(candidates)} → {len(kept)} after correlation")
        return kept

    # ── STAGE 4: TIER CLASSIFICATION ────────────────
    def stage4_classify(self, candidates: list[dict],
                        backtest_results: dict[str, dict] = None) -> list[dict]:
        """Assign TIER_1/2/3 based on backtest metrics or spread fallback."""
        for c in candidates:
            pair = c["pair"]

            if backtest_results and pair in backtest_results:
                bt = backtest_results[pair]
                sr = bt.get("single_run", {})
                sharpe = sr.get("sharpe", 0)
                pf = sr.get("profit_factor", 0)
            else:
                # Fallback: spread-based estimate
                sp = c.get("avg_spread", 0) * 10_000
                sharpe = 2.0 if sp < 1.0 else (1.5 if sp < 1.5 else 1.0)
                pf = 2.0 if sp < 1.0 else (1.6 if sp < 1.5 else 1.2)

            if sharpe >= 1.8 and pf >= 2.0:
                c["tier"] = "TIER_1"
            elif sharpe >= 1.3 and pf >= 1.6:
                c["tier"] = "TIER_2"
            else:
                c["tier"] = "TIER_3"

        t1 = sum(1 for c in candidates if c["tier"] == "TIER_1")
        t2 = sum(1 for c in candidates if c["tier"] == "TIER_2")
        logger.info(f"Stage 4: TIER_1={t1} | TIER_2={t2} | TIER_3={len(candidates)-t1-t2}")
        return candidates

    # ── FULL SCREEN ────────────────────────────────
    def screen(self, backtest_results: dict = None) -> dict:
        """Run all stages. Returns deployable candidates."""
        logger.info("Starting universe screen...")

        s1 = self.stage1_filter()
        s2 = self.stage2_rank(s1)
        s3 = self.stage3_correlation(s2)
        s4 = self.stage4_classify(s3, backtest_results)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tier_1": [c for c in s4 if c["tier"] == "TIER_1"],
            "tier_2": [c for c in s4 if c["tier"] == "TIER_2"],
            "tier_3": [c for c in s4 if c["tier"] == "TIER_3"],
        }

    def weekly_refresh(self) -> dict:
        """Weekly re-screen."""
        logger.info("Weekly refresh")
        return self.screen()


screener = UniverseScreener()
