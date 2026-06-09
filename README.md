# Statistisches Referenz-Desk (Statistical Reference Desk)

Ein schwebendes Overlay für R/Python-Statistik-Spickzettel und Dataset-Browser/Downloader mit Rdatasets, Hugging Face und Kaggle.

An interactive floating overlay for R/Python statistics cheat sheets and a dataset browser/downloader with Rdatasets, Hugging Face and Kaggle support.

**Repository:** https://github.com/Karim-Termanini/stats-sheets

---

## Requirements

- **Python 3** (stdlib only for the server)
- **A web browser** (Chromium, Chrome, Firefox, or any browser via `xdg-open`)
- **Linux** (any desktop: GNOME, KDE, XFCE, Hyprland, etc.)

Optional: `R` (RData/RDS export), Kaggle API token, `pyarrow` (Parquet)

---

## Quick start (any Linux desktop)

```bash
git clone https://github.com/Karim-Termanini/stats-sheets.git
cd stats-sheets
./launch-stats-sheets.sh
```

This starts a local server on `127.0.0.1` and opens the app in a browser window.

### Application menu entry

```bash
./install-desktop-entry.sh
```

Then launch **Statistical Reference Desk** from your desktop environment's app menu.

### Global keyboard shortcut (Super+Shift+S)

```bash
./install-keyboard-shortcut.sh
```

Supports GNOME (gsettings), Hyprland (`hyprland.conf`), and KDE when available. Other desktops: follow the printed manual instructions.

### Server only (open URL yourself)

```bash
./launch-stats-sheets.sh --server-only
# Open http://127.0.0.1:18700/ in your browser
```

Runtime cache and optional Kaggle venv are created under `~/.cache/stats-sheets/` on first launch.

---

## Features

- **Spickzettel / Cheat Sheet** — R/Python-Code-Snippets für deskriptive Statistik, Hypothesentests, Regression, ANOVA und Visualisierung
- **Dataset-Browser** — Durchsuche 3500+ Rdatasets, Hugging Face Datasets und Kaggle Datasets
- **Dataset-Preview** — Zeige die ersten 10 Zeilen eines Datasets direkt in der App an
- **Download & Konvertierung** — Lade Datasets als CSV, JSON, RData oder RDS herunter
- **Integrationscode** — Automatisch generierte R/Python-Code-Snippets für jedes Dataset
- **Mehrsprachig** — Deutsch, Englisch, Arabisch (RTL-Support)

---

## Optional: Hyprland + Waybar

For a floating overlay toggled from Waybar on Hyprland, use `toggle-stats-sheets.sh` instead of `launch-stats-sheets.sh`.

### 1. Hyprland Konfiguration

Add to `~/.config/hypr/hyprland.conf`:

```text
# stats-sheets Overlay Window Rules
windowrulev2 = float, class:^(stats-overlay)$
windowrulev2 = center, class:^(stats-overlay)$
windowrulev2 = size 1050 750, class:^(stats-overlay)$
```

### 2. Waybar Konfiguration

Add `"custom/stats_sheets"` to `modules-center` or `modules-right` in `~/.config/waybar/config.jsonc`:

```jsonc
"custom/stats_sheets": {
    "format": "📐",
    "on-click": "/home/karimorachy/Projects/stats-sheets/toggle-stats-sheets.sh",
    "tooltip-format": "Statistik Spickzettel & Datensätze"
}
```

### 3. Waybar Styling

```css
#custom-stats_sheets {
    margin: 0 7.5px;
    color: #89b4fa;
    font-size: 14px;
}
```

---

## Usage

- **Launch:** `./launch-stats-sheets.sh`, app menu, or **Super+Shift+S** (after `install-keyboard-shortcut.sh`)
- **Esc** closes the window when launched in app mode (Chromium `--app`)
- **Spickzettel-Tab** — Klicke auf Code-Blöcke zum Kopieren
- **Datasets-Tab** — Suche, filtere nach Quelle, **Favoriten**, **Zuletzt**; klicke auf ein Dataset für Details
- **Preview** — Zeige die ersten 10 Zeilen vor dem Download
- **Download** — Wähle Format (CSV/JSON/RData/RDS) und Zielordner
- **Sprache** — Umschaltbar zwischen DE / EN / AR via Dropdown
- **Tastaturnavigation** — Tab + Pfeiltasten in der Dataset-Liste

---

## Projektstruktur

| Datei | Zweck |
|---|---|
| `launch-stats-sheets.sh` | **Main launcher** — start server + open browser |
| `install-desktop-entry.sh` | App menu shortcut |
| `install-keyboard-shortcut.sh` | Global shortcut installer (Super+Shift+S) |
| `toggle-stats-sheets.sh` | Optional Hyprland/Waybar toggle |
| `index.html` | Haupt-UI |
| `script.js` | Frontend-Logik |
| `server.py` | Python-Backend (HTTP API + static UI) |
| `styles.css` | Catppuccin-Theme |
| `de.json` / `en.json` / `ar.json` | Übersetzungen |
| `stats_sheets/` | Python modules (security, config, rdatasets, …) |
| `js/storage.js` | Favorites & recent downloads (localStorage) |
| `run-tests.sh` | Local test runner (use when GitHub Actions unavailable) |
| `check_locales.py` | Locale key parity check (de/en/ar) |
| `assets/icon.svg` | App icon |

## Abhängigkeiten

- Python 3 (stdlib: `http.server`, json, csv, urllib)
- Optional: Kaggle CLI (auto-installed in `~/.cache/stats-sheets/venv/`)
- Optional: `R` (für RData/RDS-Konvertierung)

## Tests

```bash
./run-tests.sh
```

Or manually:

```bash
python -m unittest test_server_security.py -v
python check_locales.py
```

## Lizenz

GPL-3
