from mt5linux import MetaTrader5
from loguru import logger
import asyncio
from typing import Callable

REAL_PAIRS = ['EURUSDm','GBPUSDm','USDJPYm','AUDUSDm','USDCADm','USDCHFm','EURJPYm','GBPJPYm','AUDJPYm','CADJPYm']
OTC_PAIRS  = ['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCAD','USDCHF','EURJPY','GBPJPY','AUDJPY','CADJPY']

class MT5Bridge:
    def __init__(self, port: int, pairs: list):
        self.port = port
        self.pairs = pairs
        self.mt5 = MetaTrader5(host="localhost", port=self.port)
        self.connected = False
        self._last_ticks = {}

    def connect(self) -> bool:
        if self.mt5.initialize():
            self.connected = True
            for p in self.pairs:
                self.mt5.symbol_select(p, True)
            logger.info(f"Connected to Bridge on Port {self.port}")
            return True
        return False

    def _pip_factor(self, symbol: str) -> int:
        return 100 if 'JPY' in symbol else 10000

    def _is_valid_tick(self, tick) -> bool:
        return tick is not None and tick.bid > 0.0 and tick.ask > 0.0 and tick.ask > tick.bid

    async def listen(self, callback: Callable, stream_type: str, interval: float):
        logger.info(f"Starting {stream_type} listener on port {self.port}")
        while True:
            if not self.connected:
                await asyncio.sleep(interval)
                continue
            for symbol in self.pairs:
                try:
                    tick = self.mt5.symbol_info_tick(symbol)
                    if not self._is_valid_tick(tick):
                        logger.warning(f"{stream_type} | {symbol} | invalid tick skipped")
                        continue
                    last = self._last_ticks.get(symbol)
                    if last is None or tick.time != last:
                        self._last_ticks[symbol] = tick.time
                        spread = round((tick.ask - tick.bid) * self._pip_factor(symbol), 1)
                        msg = {
                            'symbol': symbol,
                            'bid': tick.bid,
                            'ask': tick.ask,
                            'spread': spread
                        }
                        await callback(msg, stream_type)
                except Exception as e:
                    logger.error(f"{stream_type} tick error {symbol}: {e}")
            await asyncio.sleep(interval)

    async def listen_real(self, callback: Callable):
        await self.listen(callback, "REAL", 1.0)

    async def listen_otc(self, callback: Callable):
        await self.listen(callback, "OTC", 0.1)

real_bridge = MT5Bridge(port=5551, pairs=REAL_PAIRS)
otc_bridge  = MT5Bridge(port=5555, pairs=OTC_PAIRS)
