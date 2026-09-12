import asyncio
from core.orchestrator import orchestrator
from loguru import logger

async def run_dry_run():
    logger.info("--- Starting Pipeline Dry Run ---")
    
    # 1. Simulate REAL (Forex) Tick
    logger.info("Injecting Synthetic REAL Tick (EURUSD)...")
    await orchestrator.handle_tick({"symbol": "EURUSD", "bid": 1.0850, "spread": 0.8}, "REAL")
    
    # 2. Simulate OTC (Binary) Tick
    logger.info("Injecting Synthetic OTC Tick (EURUSD_otc)...")
    await orchestrator.handle_tick({"symbol": "EURUSD_otc", "bid": 1.0850, "spread": 0.9}, "OTC")
    
    logger.info("--- Dry Run Complete ---")

if __name__ == "__main__":
    asyncio.run(run_dry_run())
