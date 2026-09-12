"""
QES Health Monitor — Production
Monitors all components, composite score, Telegram alerts.
"""
import psutil
import sqlite3
import time
import socket
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger
from configs.settings import settings


class HealthMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.components = {
            "Infrastructure": [
                "MT5 Terminal 1 (OTC)",
                "MT5 Terminal 2 (REAL)",
                "MT5 RPC Port",
                "Twelve Data API",
                "ForexFactory scraper",
                "VPS CPU/RAM/Disk",
            ],
            "Agents": [
                "Researcher",
                "Auditor",
                "Evolver",
                "Memory",
                "Binary Researcher",
                "Binary Auditor",
            ],
            "Services": [
                "Signal Engine Forex",
                "Signal Engine Binary",
                "Regime Classifier",
                "Pocket Manager",
                "Dashboard WebSocket",
                "Telegram Bot",
                "APScheduler",
                "Stream Controller",
            ],
            "Databases": [
                "All 6 memory DBs",
                "vault/strategies.db",
            ],
        }
        logger.info("HealthMonitor init")

    # ── CHECKS ──────────────────────────────────────────
    def _check_vps(self) -> dict:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        return {
            "cpu": cpu,
            "ram": ram,
            "disk": disk,
            "status": "🟢" if cpu < 80 and ram < 80 and disk < 90 else "🔴",
        }

    def _check_ports(self) -> dict:
        ports = {
            "MT5 RPC": 5551,
            "Dashboard": 8000,
            "WebSocket": 8001,
        }
        result = {}
        for name, port in ports.items():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            ok = s.connect_ex(('localhost', port)) == 0
            s.close()
            result[name] = "🟢" if ok else "🔴"
        return result

    def _check_dbs(self) -> dict:
        db_paths = [
            Path(settings.MEMORY_DB_PATH).parent / f"{name}.db"
            for name in [
                "mistake_memory",
                "success_dna",
                "market_conditions",
                "execution_quality",
                "regime_log",
                "knowledge_graph",
            ]
        ]
        result = {}
        for p in db_paths:
            try:
                if p.exists():
                    with sqlite3.connect(p) as conn:
                        conn.execute("SELECT 1")
                    result[p.name] = "🟢"
                else:
                    result[p.name] = "🔴"
            except Exception:
                result[p.name] = "🔴"
        return result

    def _check_streams(self) -> dict:
        # Import inside to avoid circular imports
        try:
            from core.stream_controller import stream_controller
            return {
                "FOREX": "🟢" if stream_controller.forex_enabled else "🟡",
                "BINARY": "🟢" if stream_controller.binary_enabled else "🟡",
                "DAY": "🟢" if stream_controller.day_enabled else "🟡",
                "SWING": "🟢" if stream_controller.swing_enabled else "🟡",
                "5M": "🟢" if stream_controller.binary_5m_enabled else "🟡",
                "10M": "🟢" if stream_controller.binary_10m_enabled else "🔴",
            }
        except Exception:
            return {"error": "module not loaded"}

    def _check_agents(self) -> dict:
        # Placeholder — later each agent reports heartbeat
        agents = [
            "Researcher",
            "Auditor",
            "Evolver",
            "Memory",
            "Binary Researcher",
            "Binary Auditor",
        ]
        return {a: "🟢" for a in agents}

    # ── COMPOSITE HEALTH ────────────────────────────────
    def get_system_health(self) -> dict:
        """Full health dict for dashboard and Telegram."""
        vps = self._check_vps()
        ports = self._check_ports()
        dbs = self._check_dbs()
        streams = self._check_streams()
        agents = self._check_agents()

        # Count statuses
        all_items = list(vps.values()) + list(ports.values()) + list(dbs.values())
        red_count = sum(1 for s in all_items if s == "🔴")
        yellow_count = sum(1 for s in all_items if s == "🟡")

        # Composite score
        if red_count > 0:
            composite = "🔴"
        elif yellow_count > 2:
            composite = "🟡"
        else:
            composite = "🟢"

        # Uptime
        uptime_sec = int(time.time() - self.start_time)
        hours, remainder = divmod(uptime_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "composite": composite,
            "vps": vps,
            "ports": ports,
            "databases": dbs,
            "streams": streams,
            "agents": agents,
            "uptime": uptime_str,
            "uptime_seconds": uptime_sec,
            "alert": red_count > 0,
        }

    def get_dashboard_health(self) -> dict:
        """Simplified for dashboard top bar."""
        health = self.get_system_health()
        return {
            "status": health["composite"],
            "cpu": health["vps"]["cpu"],
            "ram": health["vps"]["ram"],
            "disk": health["vps"]["disk"],
            "uptime": health["uptime"],
            "alert": health["alert"],
        }

    def telegram_health_report(self) -> str:
        """Formatted for Telegram /health command."""
        h = self.get_system_health()
        lines = [
            f"🏥 QES System Health {h['composite']}",
            f"Uptime: {h['uptime']}",
            f"CPU: {h['vps']['cpu']}% | RAM: {h['vps']['ram']}% | Disk: {h['vps']['disk']}%",
            "",
            "🔌 Ports:",
        ]
        for name, stat in h["ports"].items():
            lines.append(f"  {name}: {stat}")

        lines.append("")
        lines.append("📊 Streams:")
        for name, stat in h["streams"].items():
            lines.append(f"  {name}: {stat}")

        if h["alert"]:
            lines.append("")
            lines.append("⚠️ ALERT: Critical components down!")

        return "\n".join(lines)


health_monitor = HealthMonitor()
