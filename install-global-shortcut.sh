#!/bin/bash
# Install a global keyboard shortcut to open stats-sheets.
# Default: Super+Shift+S
#
# Hyprland: appends bind to hyprland.conf and applies it immediately.
# GNOME: registers a custom keybinding via gsettings/dconf.
# Other DEs: prints manual setup steps.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SHORTCUT="${STATS_SHEETS_SHORTCUT:-Super+Shift+S}"
MARKER="# stats-sheets global shortcut (install-global-shortcut.sh)"
HYPR_CONF="${XDG_CONFIG_HOME:-$HOME/.config}/hypr/hyprland.conf"
DCONF_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/stats-sheets/"

if command -v hyprctl >/dev/null 2>&1; then
    LAUNCHER="$SCRIPT_DIR/toggle-stats-sheets.sh"
else
    LAUNCHER="$SCRIPT_DIR/launch-stats-sheets.sh"
fi

usage() {
    cat <<EOF
Usage: $(basename "$0") [--remove]

Install global shortcut ${SHORTCUT} -> ${LAUNCHER}

Environment:
  STATS_SHEETS_SHORTCUT   Override combo (Hyprland/GNOME binding string)
EOF
}

remove_hyprland() {
    [ -f "$HYPR_CONF" ] || return 0
    if grep -qF "$MARKER" "$HYPR_CONF"; then
        awk -v marker="$MARKER" '
            $0 ~ marker { skip=2; next }
            skip>0 { skip--; next }
            { print }
        ' "$HYPR_CONF" > "${HYPR_CONF}.tmp" && mv "${HYPR_CONF}.tmp" "$HYPR_CONF"
        echo "Removed Hyprland shortcut from $HYPR_CONF (reload Hyprland to apply)."
    fi
}

install_hyprland() {
    command -v hyprctl >/dev/null 2>&1 || return 1

    local bind_line="bind = SUPER SHIFT, S, exec, ${LAUNCHER}"
    if [ -f "$HYPR_CONF" ] && grep -qF "$MARKER" "$HYPR_CONF"; then
        echo "Hyprland shortcut already present in $HYPR_CONF"
    else
        mkdir -p "$(dirname "$HYPR_CONF")"
        {
            echo ""
            echo "$MARKER"
            echo "$bind_line"
        } >> "$HYPR_CONF"
        echo "Added ${SHORTCUT} -> toggle to $HYPR_CONF"
    fi

    hyprctl keyword bind "SUPER SHIFT,S,exec,${LAUNCHER}" 2>/dev/null || true
    echo "Hyprland: ${SHORTCUT} active for this session."
    return 0
}

install_gnome() {
    command -v gsettings >/dev/null 2>&1 || return 1
    command -v dconf >/dev/null 2>&1 || return 1

    local keys
    keys=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo "@as []")
    if ! echo "$keys" | grep -q "stats-sheets"; then
        if [ "$keys" = "@as []" ] || [ "$keys" = "[]" ]; then
            gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['${DCONF_PATH}']"
        else
            local trimmed="${keys%]*}"
            gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "${trimmed}, '${DCONF_PATH}']"
        fi
    fi

    dconf write "${DCONF_PATH}name" "'Statistical Reference Desk'"
    dconf write "${DCONF_PATH}command" "'${LAUNCHER}'"
    dconf write "${DCONF_PATH}binding" "'<Super><Shift>s'"
    echo "GNOME: ${SHORTCUT} registered (Settings → Keyboard → Custom Shortcuts)."
    return 0
}

remove_gnome() {
    command -v gsettings >/dev/null 2>&1 || return 0
    command -v dconf >/dev/null 2>&1 || return 0
    local keys
    keys=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings 2>/dev/null || echo "@as []")
    keys=$(echo "$keys" | sed "s|, '${DCONF_PATH}'||; s|'${DCONF_PATH}', ||; s|'${DCONF_PATH}'||")
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$keys"
    dconf reset -f "${DCONF_PATH}" 2>/dev/null || true
    echo "Removed GNOME custom shortcut."
}

print_manual() {
    cat <<EOF

Manual setup (${SHORTCUT}):
  Command: ${LAUNCHER}

  KDE: System Settings → Shortcuts → Custom Shortcuts → Add command
  XFCE: Settings → Keyboard → Application Shortcuts
  i3/sway: bindsym \$mod+Shift+s exec ${LAUNCHER}
EOF
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
    exit 0
fi

if [ "${1:-}" = "--remove" ]; then
    remove_hyprland
    remove_gnome
    exit 0
fi

installed=0
if install_hyprland; then installed=1; fi
if install_gnome; then installed=1; fi

if [ "$installed" -eq 0 ]; then
    echo "No supported desktop detected for automatic install."
    print_manual
    exit 0
fi

print_manual
