from configs.settings import settings

class BinaryAuditor:
    def __init__(self):
        self.wr_floor = settings.BINARY_5M_MIN_WIN_RATE
        self.ev_floor = settings.BINARY_MIN_EV

    def audit_binary(self, backtest_results: dict):
        passed = (backtest_results['win_rate'] >= self.wr_floor and 
                  backtest_results['ev'] >= self.ev_floor)
        return {"passed": passed, "results": backtest_results}

binary_auditor = BinaryAuditor()
