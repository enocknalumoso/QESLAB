#!/bin/bash
source /root/qeslab/.venv/bin/activate
export PYTHONPATH=/root/qeslab
python3 -c "from core.health_monitor import health_monitor; print(health_monitor.get_system_health())"
