#!/bin/bash
# Hyprland / Waybar toggle — optional. Generic launch: launch-spickfolio.sh

WINDOW_CLASS="spickfolio-overlay"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v hyprctl >/dev/null 2>&1 && hyprctl clients -j 2>/dev/null | jq -e '.[] | select(.class=="'"$WINDOW_CLASS"'")' >/dev/null 2>&1; then
    hyprctl dispatch closewindow "class:$WINDOW_CLASS"
    "$SCRIPT_DIR/launch-spickfolio.sh" --stop
else
    SPICKFOLIO_WM_CLASS="$WINDOW_CLASS" exec "$SCRIPT_DIR/launch-spickfolio.sh"
fi
