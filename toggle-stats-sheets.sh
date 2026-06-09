#!/bin/bash
WINDOW_CLASS="stats-overlay"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PORT_FILE="$HOME/.cache/stats-sheets/port"

if hyprctl clients -j | jq -r '.[].class' | grep -q "^$WINDOW_CLASS$"; then
    hyprctl dispatch closewindow "class:$WINDOW_CLASS"
    pkill -f "stats-sheets/server.py"
else
    if ! pgrep -f "stats-sheets/server.py" >/dev/null; then
        python "$SCRIPT_DIR/server.py" &
        for i in $(seq 1 10); do
            if [ -f "$PORT_FILE" ]; then
                break
            fi
            sleep 0.1
        done
    fi
    PORT=18700
    if [ -f "$PORT_FILE" ]; then
        PORT=$(cat "$PORT_FILE")
    fi
    chromium --app="file://${SCRIPT_DIR}/index.html?port=${PORT}" --class="$WINDOW_CLASS" &
fi
