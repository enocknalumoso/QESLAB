# QESLab — Quantitative Edge System

An open-source hybrid quantitative research and signal generation pipeline for Forex and OTC Binary markets. Built for independent traders who want institutional-grade signal research without institutional resources.

---

## What It Does

QESLab combines mathematical backtesting with LLM-driven strategy research to find, validate, and monitor statistical edges in live markets. The operator receives high-confidence signals and executes manually — the system never trades autonomously.

```
Live Tick → Signal Gates → Signal Engine → Dashboard + Telegram → Operator Executes
         ↑                                                      ↓
    MT5 Bridge                                          WIN/LOSS Feedback
         ↑                                                      ↓
  Exness + PoTrade                                     Memory + Learning DBs
```

---

## Architecture

### Infrastructure Layer (Scratch-Built)
| Component | Purpose |
|---|---|
| `core/mt5_bridge.py` | Live tick streaming via mt5linux over Wine |
| `core/orchestrator.py` | Async tick routing + signal gate enforcement |
| `core/risk_engine.py` | Kelly sizing, heat limits, DD circuit breakers |
| `core/pocket_manager.py` | WAL SQLite state, cooldown, daily briefing |
| `core/strategy_vault.py` | SQLite strategy lifecycle management |
| `core/stream_controller.py` | 6 toggleable signal streams |
| `core/backtester.py` | Walk-forward, Monte Carlo, stress test |
| `core/prop_firm_engine.py` | Prop firm challenge mode with trailing floor |

### Agent Layer (LangGraph)
| Agent | Model | Role |
|---|---|---|
| Researcher | NVIDIA DeepSeek 3.2 | Generate strategy DNA hypotheses |
| Auditor | NVIDIA DeepSeek 3.2 | Adversarial backtester validation |
| Evolver | Groq Llama 4 Scout | Mutate failing DNA (max 7 generations) |
| Memory Agent | Cerebras | Encode WIN/LOSS patterns to learning DBs |

### Signal Delivery
- **Dashboard** — FastAPI + WebSocket push + 5 sound notifications
- **Telegram** — Full verbose backup + operator input terminal

---

## Key Features

- **Hybrid math + LLM** — Math confirms entry first, LLM scores confidence second
- **6-gate signal chain** — Stream toggle → Prop firm → Pocket manager → Risk engine → Spread → Confidence
- **Strategy lifecycle** — IDEA → GENERATED → BACKTESTED → AUDITED → FORWARD_TESTING → LIVE → DEGRADED → RETIRED
- **Real-time feedback loop** — Operator WIN/LOSS via Telegram feeds memory DBs instantly
- **Prop firm mode** — Togglable trailing DD floor, news blackout, EOD close enforcement
- **Uniform cooldowns** — Every breach pauses signals and waits for operator override
- **No autonomous execution** — Operator is always the final gate

---

## Tech Stack

```
VPS:          Ubuntu 22.04 LTS | Python 3.12
Brokers:      Exness REAL (MT5) + PoTrade OTC (MT5)
Backtesting:  vectorbt + pandas + numpy
Agents:       LangGraph + LiteLLM
LLM Router:   LiteLLM — unified across all providers
LLM Providers:
  NVIDIA Build — DeepSeek 3.2 (research + audit)
  Groq         — Llama 3.3 70B + Llama 4 Scout (speed)
  Cerebras     — gpt-oss-120b (fallback + memory)
Data:         6 years OHLCV 2020-2025 | 10 pairs | M1→D1
Delivery:     FastAPI + WebSocket + Telegram Bot
Storage:      SQLite WAL (7 memory DBs + vault)
```

---

## Market Coverage

```
Forex (Exness REAL):
  EURUSDm GBPUSDm USDJPYm AUDUSDm USDCADm
  USDCHFm EURJPYm GBPJPYm AUDJPYm CADJPYm

OTC Binary (PoTrade):
  EURUSD GBPUSD USDJPY AUDUSD USDCAD
  USDCHF EURJPY GBPJPY AUDJPY CADJPY

Binary Expiries: 5M | 10M | 15M | 30M
Forex Expiry:    H1
Sessions:        London | NY | London-NY Overlap
```

---

## Risk Management

```
Risk per trade:    1% or 0.5% only
Kelly fraction:    25%
Correlation:       >70% same direction → reduce to 0.5%
Daily DD halt:     Forex 5% | Binary 10%
Weekly breaker:    Forex 10%
Prop firm mode:    5% trailing DD | 10% profit target
Cooldown:          Operator confirms every exit — no auto-resume
Consecutive loss:  5 losses → pause + Telegram warning
```

---

## Validation Requirements

No strategy reaches LIVE without passing all of:

1. vectorbt full backtest
2. Walk-forward OOS holds across all windows
3. Monte Carlo 5th percentile > 0
4. Minimum 30 OOS trades
5. IS/OOS win rate gap < 2%
6. Adversarial LLM audit (DeepSeek 3.2)
7. Minimum 30 forward trades on live stream
8. Forward win rate within 2% of backtest

---

## GPU Acceleration Targets

- Monte Carlo simulations (1000 runs per strategy per pair)
- Walk-forward backtesting across 10 pairs simultaneously
- Local LLM inference via ROCm — DeepSeek, Llama
- Feature engineering on tick-level parquet data at scale

---

## Project Status

```
✅ MT5 bridges live — both brokers ticking
✅ Orchestrator running — asyncio production loop
✅ Signal engines active — Forex + Binary
✅ Risk engine wired — Kelly + heat + DD
✅ Pocket manager active — WAL SQLite
✅ Strategy vault operational
✅ Stream controller — 6 toggleable streams
✅ Backtester complete — walk-forward + MC + stress
⚠️  Agent layer — LangGraph build in progress
⚠️  Forward tester — in progress
⚠️  News feed integration — planned
```

---

## Core Philosophy

```
Mathematics is sovereign
LLMs are constrained interpreters
Only validated relationships survive
The operator is the final gate
The feedback loop never stops
```

---

## License

MIT — open source, free to use, free to build on.

---

*Built by an independent developer in Kampala, Uganda.*
