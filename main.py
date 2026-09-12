import asyncio
from core.orchestrator import orchestrator
from core.mt5_bridge import real_bridge, otc_bridge
from loguru import logger

async def main():
    logger.info("Initializing QES Pipeline (Dual-Bridge Mode)...")
    
    # 1. Connect to both bridges
    if not real_bridge.connect():
        logger.error("Failed to connect to REAL Bridge (5551).")
    if not otc_bridge.connect():
        logger.error("Failed to connect to OTC Bridge (5555).")
    
    # 2. Start Orchestrator
    try:
        await orchestrator.run_forever()
    except Exception as e:
        logger.critical(f"Pipeline Crash: {e}")

if __name__ == "__main__":
    asyncio.run(main())
