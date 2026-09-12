"""
QES Signal Formatter — Production
Dynamic formatting, UTC → EAT conversion, RR, lot, risk calculation.
"""
from datetime import datetime, timezone, timedelta
from configs.settings import settings


def format_forex(signal: dict) -> str:
    """Format Forex signal for Telegram/dashboard."""
    # Time conversion UTC → EAT (UTC+3)
    created = datetime.fromisoformat(signal["created_at"])
    eat_created = (created + timedelta(hours=3)).strftime("%H:%M")
    expiry = datetime.fromisoformat(signal["expires_at"])
    eat_expiry = (expiry + timedelta(hours=3)).strftime("%H:%M")

    # Lot size (already calculated by risk engine)
    lot = signal.get("lot_size", 0.01)
    risk_pct = signal.get("risk_pct", 0.02) * 100  # to %
    sl = signal.get("sl", 0.0)
    tp = signal.get("tp", 0.0)
    rr = signal.get("rr", 1.5)

    # Confidence color
    conf = signal.get("confidence", 0) * 100
    if conf >= 80:
        icon = "🟢"
    elif conf >= 60:
        icon = "🟡"
    else:
        icon = "🔴"

    # Format
    return f"""{icon} {signal['pair']} {signal['direction']} [{signal['timeframe']}]
Entry: {signal['entry']:.5f} | SL: {sl:.5f} | TP: {tp:.5f}
RR: 1:{rr} | Lot: {lot} | Risk: {risk_pct:.1f}%
Confidence: {conf:.0f}% | WR: {signal.get('win_rate', 0)*100:.1f}% ({signal.get('total_trades', 0)}T)
Expires: {eat_expiry} EAT / {expiry.strftime('%H:%M')} UTC
[ ✅ WIN ] [ ❌ LOSS ] [ ➡️ BE ] [ ⏭ SKIP ]"""


def format_binary(signal: dict) -> str:
    """Format Binary signal for Telegram/dashboard."""
    created = datetime.fromisoformat(signal["created_at"])
    eat_created = (created + timedelta(hours=3)).strftime("%H:%M")
    expiry = datetime.fromisoformat(signal["expires_at"])
    eat_expiry = (expiry + timedelta(hours=3)).strftime("%H:%M")

    ev = signal.get("ev", 0.0)
    conf = signal.get("confidence", 0) * 100
    wr = signal.get("win_rate", 0) * 100

    if ev > 0.15:
        icon = "🟢"
    elif ev > 0.08:
        icon = "🟡"
    else:
        icon = "🔴"

    stake = signal.get("stake", 0.0)
    return f"""{icon} {signal['pair']} {signal['direction']} [{signal['expiry_min']}M]
Entry: {signal['entry']:.5f} | Expiry: {signal['expiry_min']} min
EV: +{ev:.2f}¢ | Confidence: {conf:.0f}% | WR: {wr:.1f}%
Stake: {stake:.2f} | Created: {eat_created} EAT
[ ✅ WIN ] [ ❌ LOSS ] [ ➡️ BE ] [ ⏭ SKIP ]"""


def format_for_dashboard(signal: dict) -> dict:
    """JSON-friendly format for WebSocket."""
    created = datetime.fromisoformat(signal["created_at"])
    expiry = datetime.fromisoformat(signal["expires_at"])
    now = datetime.now(timezone.utc)

    # Countdown seconds
    countdown = int((expiry - now).total_seconds())
    if countdown < 0:
        countdown = 0

    return {
        "id": signal.get("signal_id"),
        "stream": signal.get("stream", "FOREX"),
        "pair": signal.get("pair"),
        "direction": signal.get("direction"),
        "timeframe": signal.get("timeframe"),
        "expiry_min": signal.get("expiry_min"),
        "entry": signal.get("entry"),
        "sl": signal.get("sl"),
        "tp": signal.get("tp"),
        "lot": signal.get("lot_size"),
        "risk_pct": signal.get("risk_pct"),
        "confidence": signal.get("confidence"),
        "win_rate": signal.get("win_rate"),
        "total_trades": signal.get("total_trades"),
        "ev": signal.get("ev", 0.0),
        "stake": signal.get("stake", 0.0),
        "created_at": signal["created_at"],
        "expires_at": signal["expires_at"],
        "countdown": countdown,
        "status": signal.get("status", "ACTIVE"),
        "buttons": ["WIN", "LOSS", "BE", "SKIP"],
    }
