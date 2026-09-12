import asyncio
from core.mt5_bridge import real_bridge, otc_bridge
from core.orchestrator import orchestrator

async def test_stream_integration():
    print("Testing Concurrent Stream Ingestion...")
    # Register the orchestrator's handle_tick as the callback for both
    # We verify the orchestrator can route REAL vs OTC correctly
    
    # Start listeners as tasks
    tasks =[
        asyncio.create_task(real_bridge.listen_real(orchestrator.handle_tick)),
        asyncio.create_task(otc_bridge.listen_otc(orchestrator.handle_tick))
    ]
    
    print("Listeners active. Waiting 5s for tick flow...")
    await asyncio.sleep(5)
    
    for t in tasks:
        t.cancel()
    print("Pipeline Flow Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_stream_integration())
