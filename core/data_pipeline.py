"""
QES Data Pipeline — Production
Reads raw tick Parquet, reconstructs bid/ask,
streams via Polars lazy, validates integrity.
"""
import polars as pl
from pathlib import Path
from datetime import datetime, timezone
from loguru import logger
from configs.settings import settings


class DataPipeline:
    """Streaming data layer. Parquet in, clean DataFrames out."""

    def __init__(self):
        self.raw_path = Path(settings.DATA_RAW_PATH)
        self.resampled_path = Path(settings.DATA_RESAMPLED_PATH)
        self.resampled_path.mkdir(parents=True, exist_ok=True)
        self.train_ratio = settings.BACKTEST_TRAIN_RATIO
        logger.info(f"Pipeline init | raw={self.raw_path} | train_ratio={self.train_ratio}")

    # ── LOAD ──────────────────────────────────────────
    def load_raw(self, pair: str) -> pl.LazyFrame:
        """Scan raw parquet, reconstruct bid/ask from mid+spread."""
        fpath = self.raw_path / f"{pair}.parquet"
        if not fpath.exists():
            raise FileNotFoundError(f"Missing raw data: {fpath}")

        lf = pl.scan_parquet(fpath)

        # Ensure required columns exist
        required = {"datetime", "open", "high", "low", "close", "volume"}
        schema_cols = set(lf.collect_schema().names())
        missing = required - schema_cols
        if missing:
            raise ValueError(f"{pair}: missing columns {missing}")

        lf = lf.with_columns(
            pl.col("datetime").cast(pl.Datetime(time_unit="us", time_zone="UTC")),
            ((pl.col("high") + pl.col("low")) / 2).alias("mid"),
            (pl.col("high") - pl.col("low")).alias("spread"),
            # Bid/Ask reconstruction
            (pl.col("close") - (pl.col("high") - pl.col("low")) / 2).alias("bid"),
            (pl.col("close") + (pl.col("high") - pl.col("low")) / 2).alias("ask"),
            pl.lit(pair).alias("pair"),
        ).sort("datetime").unique(subset=["datetime"], keep="last")

        return lf

    def load_all(self) -> dict[str, pl.LazyFrame]:
        """Load all pairs in raw/. Returns {pair: LazyFrame}."""
        pairs = [f.stem for f in self.raw_path.glob("*.parquet")]
        logger.info(f"Loading {len(pairs)} pairs: {pairs}")
        return {p: self.load_raw(p) for p in pairs}

    # ── VALIDATE ──────────────────────────────────────
    def validate(self, lf: pl.LazyFrame, pair: str) -> dict:
        """Run integrity checks. Returns dict of issues."""
        stats = (
            lf.select(
                pl.col("datetime").is_null().sum().alias("null_dt"),
                pl.col("close").is_nan().sum().alias("nan_close"),
                pl.col("close").is_null().sum().alias("null_close"),
                (pl.col("close") <= 0).sum().alias("zero_close"),
                pl.col("datetime").n_unique().alias("total_rows"),
                pl.col("datetime").min().alias("start"),
                pl.col("datetime").max().alias("end"),
                (pl.col("datetime").diff().cast(pl.Int64) <= 0).sum().alias("time_reversals"),
            )
            .collect()
            .to_dicts()[0]
        )

        issues = []
        if stats["null_dt"] > 0:
            issues.append(f"null_dt={stats['null_dt']}")
        if stats["nan_close"] > 0:
            issues.append(f"nan_close={stats['nan_close']}")
        if stats["null_close"] > 0:
            issues.append(f"null_close={stats['null_close']}")
        if stats["zero_close"] > 0:
            issues.append(f"zero_close={stats['zero_close']}")
        if stats["time_reversals"] > 0:
            issues.append(f"time_reversals={stats['time_reversals']}")

        status = "PASS" if not issues else "FAIL"
        logger.info(f"Validate {pair}: {status} | rows={stats['total_rows']} | "
                     f"{stats['start']} → {stats['end']}")
        if issues:
            logger.warning(f"  Issues: {issues}")

        return {"pair": pair, "status": status, "issues": issues, **stats}

    def validate_all(self) -> list[dict]:
        """Run validate() on every pair."""
        results = []
        for fpath in sorted(self.raw_path.glob("*.parquet")):
            pair = fpath.stem
            lf = self.load_raw(pair)
            results.append(self.validate(lf, pair))
        return results

    # ── SPLIT ─────────────────────────────────────────
    def split_train_oos(self, lf: pl.LazyFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Chronological 70/30 split. Returns (train, oos) as eager DataFrames."""
        df = lf.collect()
        split_idx = int(len(df) * self.train_ratio)
        train = df.slice(0, split_idx)
        oos = df.slice(split_idx, len(df) - split_idx)
        logger.info(f"Split: train={len(train)} | oos={len(oos)} | "
                     f"ratio={len(train)/len(df):.1%}")
        return train, oos

    # ── SUMMARY ───────────────────────────────────────
    def summary(self) -> dict:
        """Quick overview of all data."""
        results = {}
        for fpath in sorted(self.raw_path.glob("*.parquet")):
            pair = fpath.stem
            size_mb = fpath.stat().st_size / (1024 * 1024)
            lf = self.load_raw(pair)
            stats = (
                lf.select(
                    pl.col("datetime").min().alias("start"),
                    pl.col("datetime").max().alias("end"),
                    pl.col("datetime").n_unique().alias("rows"),
                )
                .collect()
                .to_dicts()[0]
            )
            results[pair] = {**stats, "size_mb": round(size_mb, 1)}
        return results


# Singleton
pipeline = DataPipeline()
