# Statistisches Referenz-Desk (Statistical Reference Desk)

Ein浮es Overlay für R/Python-Statistik-Spickzettel und Dataset-Browser/Downloader mit Rdatasets, Hugging Face und Kaggle.

An interactive floating overlay for R/Python statistics cheat sheets and a dataset browser/downloader with Rdatasets, Hugging Face and Kaggle support.

---

## Features

- **Spickzettel / Cheat Sheet** — R/Python-Code-Snippets für deskriptive Statistik, Hypothesentests, Regression, ANOVA und Visualisierung
- **Dataset-Browser** — Durchsuche 3500+ Rdatasets, Hugging Face Datasets und Kaggle Datasets
- **Dataset-Preview** — Zeige die ersten 10 Zeilen eines Datasets direkt in der App an
- **Download & Konvertierung** — Lade Datasets als CSV, JSON, RData oder RDS herunter
- **Integrationscode** — Automatisch generierte R/Python-Code-Snippets für jedes Dataset
- **Mehrsprachig** — Deutsch, Englisch, Arabisch (RTL-Support)

## Setup & Integration

### 1. Hyprland Konfiguration

Add these lines to the bottom of `~/.config/hypr/hyprland.conf`:

```text
# stats-sheets Overlay Window Rules
windowrulev2 = float, class:^(stats-overlay)$
windowrulev2 = center, class:^(stats-overlay)$
windowrulev2 = size 1050 750, class:^(stats-overlay)$
```

### 2. Waybar Konfiguration

Add `"custom/stats_sheets"` to `modules-center` or `modules-right` in `~/.config/waybar/config.jsonc`:

```jsonc
"modules-center": [
    "custom/stats_sheets",
    // ...
],
```

```jsonc
"custom/stats_sheets": {
    "format": "📐",
    "on-click": "/home/karimorachy/Projects/stats-sheets/toggle-stats-sheets.sh",
    "tooltip-format": "Statistik Spickzettel & Datensätze"
}
```

### 3. Waybar Styling

Add to `~/.config/waybar/style.css`:

```css
#custom-stats_sheets {
    margin: 0 7.5px;
    color: #89b4fa;
    font-size: 14px;
}
```

## Usage

- Klicke das **📐**-Symbol in Waybar, um das Overlay zu öffnen/schließen
- **Esc** schließt das Overlay
- **Spickzettel-Tab** — Klicke auf Code-Blöcke zum Kopieren
- **Datasets-Tab** — Suche, filtere nach Quelle (R/HF/Kaggle), klicke auf ein Dataset für Details
- **Preview** — Zeige die ersten 10 Zeilen vor dem Download
- **Download** — Wähle Format (CSV/JSON/RData/RDS) und Zielordner
- **Sprache** — Umschaltbar zwischen DE / EN / AR via Dropdown
- **Tastaturnavigation** — Tab + Pfeiltasten in der Dataset-Liste

## Projektstruktur

| Datei | Zweck |
|---|---|
| `index.html` | Haupt-UI |
| `script.js` | Frontend-Logik |
| `server.py` | Python-Backend (HTTP API) |
| `styles.css` | Catppuccin-Theme |
| `de.json` / `en.json` / `ar.json` | Übersetzungen |
| `rdatasets.csv` | Gecachter Rdatasets-Katalog |
| `toggle-stats-sheets.sh` | Waybar-Toggle-Script |

## Abhängigkeiten

- Python 3 (stdlib only: http.server, json, csv, urllib)
- Optional: `kaggle` CLI (in `venv/`) für Kaggle-Suche/Download
- Optional: `R` (für RData/RDS-Konvertierung)

## Lizenz

GPL-3
