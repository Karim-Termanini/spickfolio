#!/bin/bash
# Start the local server and open stats-sheets in a browser window.
# Works on any Linux desktop (GNOME, KDE, XFCE, Hyprland, etc.).

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CACHE_DIR="$HOME/.cache/stats-sheets"
PORT_FILE="$CACHE_DIR/port"
PID_FILE="$CACHE_DIR/server.pid"
DEFAULT_PORT=18700

stop_server() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
        fi
        rm -f "$PID_FILE"
    fi
}

server_running() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        kill -0 "$pid" 2>/dev/null && return 0
    fi
    return 1
}

ensure_server() {
    if server_running; then
        return 0
    fi
    python "$SCRIPT_DIR/server.py" &
    for _ in $(seq 1 30); do
        if [ -f "$PORT_FILE" ]; then
            return 0
        fi
        sleep 0.1
    done
    echo "stats-sheets: server failed to start" >&2
    return 1
}

get_port() {
    if [ -f "$PORT_FILE" ]; then
        cat "$PORT_FILE"
    else
        echo "$DEFAULT_PORT"
    fi
}

open_browser() {
    local url="$1"
    local wm_class="${2:-}"

    if [ -n "$wm_class" ]; then
        for cmd in chromium google-chrome-stable google-chrome; do
            if command -v "$cmd" >/dev/null 2>&1; then
                "$cmd" --app="$url" --class="$wm_class" &
                return 0
            fi
        done
    fi

    for cmd in chromium google-chrome-stable google-chrome microsoft-edge brave; do
        if command -v "$cmd" >/dev/null 2>&1; then
            "$cmd" --app="$url" &
            return 0
        fi
    done

    if command -v firefox >/dev/null 2>&1; then
        firefox --new-window "$url" &
        return 0
    fi

    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" &
        return 0
    fi

    echo "stats-sheets: no browser found. Open $url manually." >&2
    return 1
}

if [ "${1:-}" = "--stop" ]; then
    stop_server
    exit 0
fi

if [ "${1:-}" = "--server-only" ]; then
    if server_running; then
        echo "http://127.0.0.1:$(get_port)/"
        exit 0
    fi
    exec python "$SCRIPT_DIR/server.py"
fi

ensure_server || exit 1
PORT=$(get_port)
URL="http://127.0.0.1:${PORT}/"
open_browser "$URL" "${STATS_SHEETS_WM_CLASS:-}"
