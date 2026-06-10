#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/spickfolio.desktop"

mkdir -p "$APPS_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=spickFolio
Name[de]=spickFolio
Comment=R/Python statistics cheat sheet and dataset browser
Comment[de]=R/Python Statistik-Spickzettel und Dataset-Browser
Exec=${SCRIPT_DIR}/launch-spickfolio.sh
Icon=${SCRIPT_DIR}/assets/icon.svg
Terminal=false
Categories=Education;Science;Development;
Keywords=statistics;R;Python;datasets;cheat sheet;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo "Installed: $DESKTOP_FILE"
