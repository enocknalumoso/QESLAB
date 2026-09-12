import asyncio
from core.mt5_bridge import real_bridge, otc_bridge
from agents.signal_engine import signal_engine
from agents.binary_signal_eng import binary_signal_engine
from core.strategy_vault import strategy_vault
from signals.formatter import format_forex, format_binary
from loguru import logger

class Orchestrator:
    def __init__(self):
        self.active_forex_strats = []
        self.active_binary_strats =[]

    def refresh_vault(self):
        self.active_forex_strats = strategy_vault.get_active_strategies("FOREX")
        self.active_binary_strats = strategy_vault.get_active_strategies("BINARY")

    async def handle_tick(self, msg, stream_type):
        pair = msg.get('symbol')
        price = msg.get('bid')
        spread = msg.get('spread', 0.0)

        if stream_type == "REAL":
            signal = signal_engine.process_live_data(pair, "H1", price, {"risk": 0.02})
            if signal:
                logger.info(f"FOREX SIGNAL: {pair} | Spread: {spread}")
        elif stream_type == "OTC":
            signals = binary_signal_engine.process_tick(pair, price, self.active_binary_strats)
            for sig in signals:
                logger.info(f"BINARY SIGNAL: {pair} | {sig['direction']} | Spread: {spread}")

    async def run_forever(self):
        logger.info("QESLAB Orchestrator Starting...")
        self.refresh_vault()
        await asyncio.gather(
            real_bridge.listen_real(self.handle_tick),
            otc_bridge.listen_otc(self.handle_tick)
        )

orchestrator = Orchestrator()
