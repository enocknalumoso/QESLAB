"""
QES Resampler — Production
15 timeframes, validated output, checkpoint aware.
Uses data_pipeline for bid/ask-aware source data.
"""
import polars as pl
from pathlib import Path
from datetime import datetime, timezone
from loguru import logger
from core.data_pipeline import pipeline


class Resampler:
    """Resamples raw tick data to 15 standard timeframes."""

    TIMEFRAMES = {
        "M1": "1m", "M2": "2m", "M3": "3m",
        "M5": "5m", "M10": "10m", "M15": "15m",
        "M30": "30m",
        "H1": "1h", "H2": "2h", "H4": "4h",
        "H6": "6h", "H8": "8h", "H12": "12h",
        "D1": "1d", "W1": "1w",
    }

    def __init__(self):
        self.out_path = pipeline.resampled_path
        self.out_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Resampler init | output={self.out_path}")

    # ── CORE RESAMPLE ─────────────────────────────────
    def resample_single(self, pair: str, tf_key: str, lf: pl.LazyFrame) -> pl.DataFrame:
        """Resample one pair to one timeframe."""
        interval = self.TIMEFRAMES[tf_key]

        df = (
            lf.with_columns(
                pl.col("datetime").cast(pl.Datetime(time_unit="us", time_zone="UTC"))
            )
            .group_by_dynamic("datetime", every=interval, start_by="datapoint")
            .agg([
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
                pl.col("spread").mean().alias("avg_spread"),
                pl.col("bid").first().alias("bid_open"),
                pl.col("ask").first().alias("ask_open"),
            ])
            .sort("datetime")
            .collect()
        )

        # Drop rows where open is null (first incomplete bar)
        df = df.filter(pl.col("open").is_not_null())
        return df

    # ── BATCH RESAMPLE ALL ────────────────────────────
    def resample_all(self, pair: str):
        """Resample one pair to all 15 timeframes. Write Parquet."""
        logger.info(f"Resampling {pair} → 15 timeframes...")
        lf = pipeline.load_raw(pair)

        written = 0
        for tf_key in self.TIMEFRAMES:
            out_file = self.out_path / f"{pair}_{tf_key}.parquet"

            # Skip if file newer than source (checkpointing)
            src_file = pipeline.raw_path / f"{pair}.parquet"
            if out_file.exists() and src_file.exists():
                if out_file.stat().st_mtime >= src_file.stat().st_mtime:
                    logger.debug(f"  Skip {tf_key} (up to date)")
                    continue

            df = self.resample_single(pair, tf_key, lf)
            df.write_parquet(out_file)
            written += 1

        logger.info(f"  {pair}: {written} written, {len(self.TIMEFRAMES) - written} skipped")

    # ── RESAMPLE ALL PAIRS ────────────────────────────
    def resample_all_pairs(self):
        """Resample every pair in raw/ to all timeframes."""
        pairs = sorted([f.stem for f in pipeline.raw_path.glob("*.parquet")])
        logger.info(f"Resampling {len(pairs)} pairs × {len(self.TIMEFRAMES)} TFs...")

        for i, pair in enumerate(pairs, 1):
            logger.info(f"[{i}/{len(pairs)}] {pair}")
            self.resample_all(pair)

        logger.info("Resample complete.")

    # ── VALIDATE OUTPUT ───────────────────────────────
    def validate_resampled(self, pair: str) -> dict:
        """Check all 15 TFs for a pair exist and have data."""
        results = {}
        for tf_key in self.TIMEFRAMES:
            fpath = self.out_path / f"{pair}_{tf_key}.parquet"
            if not fpath.exists():
                results[tf_key] = "MISSING"
                continue
            try:
                df = pl.read_parquet(fpath)
                rows = df.height
                col_names = df.columns
                required = {"datetime", "open", "high", "low", "close", "volume"}
                missing_cols = required - set(col_names)
                if missing_cols:
                    results[tf_key] = f"MISSING_COLS: {missing_cols}"
                elif rows < 10:
                    results[tf_key] = f"LOW_ROWS: {rows}"
                else:
                    start = df["datetime"][0]
                    end = df["datetime"][-1]
                    results[tf_key] = f"OK ({rows} bars, {start} → {end})"
            except Exception as e:
                results[tf_key] = f"CORRUPT: {e}"
        return results

    # ── SUMMARY ───────────────────────────────────────
    def summary(self) -> dict:
        """Count files in resampled/."""
        files = list(self.out_path.glob("*.parquet"))
        pairs = set(f.stem.split("_")[0] for f in files)
        return {
            "path": str(self.out_path),
            "pairs": len(pairs),
            "files": len(files),
            "expected": len(pairs) * len(self.TIMEFRAMES),
        }


# Singleton
resampler = Resampler()
