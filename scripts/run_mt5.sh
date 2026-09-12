#!/bin/bash
export WINEPREFIX=/root/.mt5
export DISPLAY=:1

# 1. Start Virtual Display if not running
if ! pgrep -x "Xvfb" > /dev/null; then
    Xvfb :1 -screen 0 1024x768x16 &
    sleep 2
fi

# 2. Start the RPyC Bridge Server (Crucial for Port 18812)
logger "Starting QES MT5 Bridge Server..."
wine /root/.mt5/drive_c/python39/python.exe -m rpyc.cli.rpyc_classic --port 18812 &

# 3. Start MetaTrader 5 in Portable Mode
logger "Starting MetaTrader 5..."
wine "/root/.mt5/drive_c/Program Files/MetaTrader 5/terminal64.exe" /portable &
