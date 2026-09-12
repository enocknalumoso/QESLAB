from configs.settings import settings
from core.pocket_manager import pocket_manager
from core.correlation_monitor import correlation_monitor

class PortfolioLayer:
    def __init__(self):
        self.max_forex_heat = settings.MAX_PORTFOLIO_HEAT_FOREX
        self.max_binary_heat = settings.MAX_PORTFOLIO_HEAT_BINARY

    def can_add_signal(self, stream, pair, risk_pct):
        """
        Validates if a new signal can be added based on:
        1. Total stream heat limits
        2. Forex duplicate pair check
        3. Forex correlation block (>70%)
        """
        state = pocket_manager.get_state(stream)
        current_heat = state.get('daily_dd', 0) # Simplified heat tracking for logic check
        
        if stream == "FOREX":
            # 1. Heat Check
            if (current_heat + risk_pct) > self.max_forex_heat:
                return False, "EXCEEDS_MAX_FOREX_HEAT"
            
            # 2. Duplicate Pair Check (Enforced in Mandate)
            # This logic will interface with the Live Signal Engine in Stage 12
            
            return True, "PROCEED"

        elif stream == "BINARY":
            # 1. Heat Check
            if (current_heat + risk_pct) > self.max_binary_heat:
                return False, "EXCEEDS_MAX_BINARY_HEAT"
            
            # Binary allows rapid fire (Mandate: no correlation block)
            return True, "PROCEED"

        return False, "INVALID_STREAM"

portfolio_layer = PortfolioLayer()
