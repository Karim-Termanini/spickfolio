#!/bin/bash
# Install a global keyboard shortcut to launch stats-sheets.
# Default: Super+Shift+S

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCHER="$SCRIPT_DIR/launch-stats-sheets.sh"
BINDING="${STATS_SHEETS_BINDING:-<Super><Shift>s}"
HYPR_BIND="bind = SUPER SHIFT, S, exec, ${LAUNCHER}"
MARKER="# stats-sheets keyboard shortcut"

installed=0

install_gnome() {
    if ! command -v gsettings >/dev/null 2>&1; then
        return 1
    fi
    if ! gsettings list-schemas 2>/dev/null | grep -q 'org.gnome.settings-daemon.plugins.media-keys'; then
        return 1
    fi

    local schema="org.gnome.settings-daemon.plugins.media-keys"
    local path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/stats-sheets/"
    local custom="org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:${path}"

    local keys
    keys=$(gsettings get "$schema" custom-keybindings 2>/dev/null || echo "@as []")
    if ! echo "$keys" | grep -q "stats-sheets"; then
        if [ "$keys" = "@as []" ] || [ "$keys" = "[]" ]; then
            gsettings set "$schema" custom-keybindings "['${path}']"
        else
            keys=${keys%]*}
            gsettings set "$schema" custom-keybindings "${keys}, '${path}']"
        fi
    fi

    gsettings set "$custom" name "Statistical Reference Desk"
    gsettings set "$custom" command "$LAUNCHER"
    gsettings set "$custom" binding "$BINDING"
    echo "GNOME shortcut installed: $BINDING"
    installed=1
}

install_hyprland() {
    local conf="${XDG_CONFIG_HOME:-$HOME/.config}/hypr/hyprland.conf"
    if [ ! -f "$conf" ]; then
        return 1
    fi
    if grep -qF "$MARKER" "$conf" 2>/dev/null; then
        echo "Hyprland shortcut already present in $conf"
        installed=1
        return 0
    fi
    {
        echo ""
        echo "$MARKER"
        echo "$HYPR_BIND"
    } >> "$conf"
    echo "Hyprland shortcut added to $conf (Super+Shift+S)"
    echo "Run: hyprctl reload"
    installed=1
}

install_kde() {
    if ! command -v kwriteconfig6 >/dev/null 2>&1; then
        return 1
    fi
    local file="${XDG_CONFIG_HOME:-$HOME/.config}/kglobalshortcutsrc"
    kwriteconfig6 --file "$file" --group "services/org.kde.stats-sheets.desktop" --key "_kde" "1"
    kwriteconfig6 --file "$file" --group "services/org.kde.stats-sheets.desktop" --key "_launch" "Meta+Shift+S,none,Statistical Reference Desk"
    if command -v qdbus >/dev/null 2>&1; then
        qdbus org.kde.kglobalaccel /component/kglobalaccel org.kde.kglobalaccel.KGlobalAccel.reloadConfig 2>/dev/null || true
    fi
    echo "KDE shortcut registered (Meta+Shift+S) — assign in System Settings if needed"
    installed=1
}

install_gnome || true
install_hyprland || true
install_kde || true

if [ "$installed" -eq 0 ]; then
    echo "Could not auto-install a shortcut for this desktop environment."
    echo ""
    echo "Manual setup:"
    echo "  1. Open your desktop Settings → Keyboard → Custom Shortcuts"
    echo "  2. Add command: $LAUNCHER"
    echo "  3. Assign: Super+Shift+S (or any key you prefer)"
    exit 0
fi

echo ""
echo "Shortcut command: $LAUNCHER"
