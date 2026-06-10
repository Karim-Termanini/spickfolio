# spickFolio

Ein schwebendes Overlay für R/Python-Statistik-Spickzettel und Dataset-Browser/Downloader mit Rdatasets, Hugging Face und Kaggle.

An interactive floating overlay for R/Python statistics cheat sheets and a dataset browser/downloader with Rdatasets, Hugging Face and Kaggle support.

**Repository:** https://github.com/Karim-Termanini/spickfolio

---

## Requirements

- **Python 3** (stdlib only for the server)
- **A web browser** (Chromium, Chrome, Firefox, or any browser via `xdg-open`)
- **Linux** (any desktop: GNOME, KDE, XFCE, Hyprland, etc.)

Optional: `R` (RData/RDS export), Kaggle API token, `pyarrow` (Parquet)

---

## Quick start (any Linux desktop)

```bash
git clone https://github.com/Karim-Termanini/spickfolio.git
cd spickfolio
./launch-spickfolio.sh
```

This starts a local server on `127.0.0.1` and opens the app in a browser window.

### Application menu entry

```bash
./install-desktop-entry.sh
```

Then launch **spickFolio** from your desktop environment's app menu.

### Global keyboard shortcut (Super+Shift+S)

```bash
./install-global-shortcut.sh
```

Hyprland and GNOME are configured automatically. Other desktops get printed setup steps. Remove with `./install-global-shortcut.sh --remove`.

### Server only (open URL yourself)

```bash
./launch-spickfolio.sh --server-only
# Open http://127.0.0.1:18700/ in your browser
```

Runtime cache and optional Kaggle venv are created under `~/.cache/spickfolio/` on first launch.

---

## Features

- **Spickzettel / Cheat Sheet** — R/Python-Code-Snippets für deskriptive Statistik, Hypothesentests, Regression, ANOVA und Visualisierung
- **Dataset-Browser** — Durchsuche 3500+ Rdatasets, Hugging Face Datasets und Kaggle Datasets
- **Dataset-Preview** — Zeige die ersten 10 Zeilen eines Datasets direkt in der App an
- **Download & Konvertierung** — Lade Datasets als CSV, JSON, RData oder RDS herunter
- **Integrationscode** — Automatisch generierte R/Python-Code-Snippets für jedes Dataset
- **Favoriten & Zuletzt** — Datasets speichern; letzte Downloads (localStorage)
- **Themes** — Dunkel, Hell, System (folgt OS)
- **Mehrsprachig** — Deutsch, Englisch, Arabisch (RTL-Support)

### Kaggle (optional)

Select the **Kaggle** source filter. If no API token is configured, the app shows step-by-step setup. Save credentials to `~/.kaggle/kaggle.json` or `~/.kaggle/access_token`, then click **Check again**.

---

## Optional: Hyprland + Waybar

For a floating overlay toggled from Waybar on Hyprland, use `toggle-spickfolio.sh` instead of `launch-spickfolio.sh`.

### 1. Hyprland Konfiguration

Add to `~/.config/hypr/hyprland.conf`:

```text
# spickFolio Overlay Window Rules
windowrulev2 = float, class:^(spickfolio-overlay)$
windowrulev2 = center, class:^(spickfolio-overlay)$
windowrulev2 = size 1050 750, class:^(spickfolio-overlay)$
```

### 2. Waybar Konfiguration

Add `"custom/spickfolio"` to `modules-center` or `modules-right` in `~/.config/waybar/config.jsonc`:

```jsonc
"custom/spickfolio": {
    "format": "📐",
    "on-click": "/home/karimorachy/Projects/spickfolio/toggle-spickfolio.sh",
    "tooltip-format": "Statistik Spickzettel & Datensätze"
}
```

### 3. Waybar Styling

```css
#custom-spickfolio {
    margin: 0 7.5px;
    color: #89b4fa;
    font-size: 14px;
}
```

---

## Usage

- **Launch:** `./launch-spickfolio.sh`, app menu, or **Super+Shift+S** (after `install-global-shortcut.sh`)
- **Esc** returns from dataset detail; closes the window in app mode (Chromium `--app`)
- **Ctrl+Shift+T** cycles theme (dark → light → system)
- **Ctrl+1 / Ctrl+2** switch Spickzettel / Datensätze tabs
- **/** focuses the search bar
- **Spickzettel-Tab** — Klicke auf Code-Blöcke zum Kopieren; ↑↓←→ zwischen Snippets, Enter/Space kopiert, ↓ aus der Suche springt ins erste Snippet
- **Datasets-Tab** — Suche, filtere nach Quelle, **Favoriten**, **Zuletzt**; ★ auf der Detailseite speichert Favoriten
- **Erster Start** — Kurzanleitung-Banner (einmalig, dismissible)
- **Fehler** — Verbindungs- und Suchfehler mit **Retry**; Rate-Limit (429) zeigt Countdown
- **Preview** — Zeige die ersten 10 Zeilen vor dem Download
- **Download** — Wähle Format (CSV/JSON/RData/RDS) und Zielordner
- **Sprache** — Umschaltbar zwischen DE / EN / AR via Dropdown
- **Datensätze-Liste:** ↑↓ navigate, Home/End jump, PgUp/PgDn skip 5, Enter/Space open; ←→ at list edges change page
- **Filter pills:** ←→ when focused

---

## Projektstruktur

| Datei | Zweck |
|---|---|
| `launch-spickfolio.sh` | **Main launcher** — start server + open browser |
| `install-desktop-entry.sh` | App menu shortcut |
| `install-global-shortcut.sh` | Global Super+Shift+S launcher (Hyprland/GNOME) |
| `toggle-spickfolio.sh` | Optional Hyprland/Waybar toggle |
| `index.html` | Haupt-UI |
| `js/*.js` | Frontend modules (datasets, cheat sheet, keyboard, storage, …) |
| `server.py` | Entry point → `spick_folio.main.run()` |
| `spick_folio/` | Backend (handler, security, config, …) |
| `styles.css` | Catppuccin-Theme, dark/light/system |
| `de.json` / `en.json` / `ar.json` | Übersetzungen |
| `js/storage.js` | Favorites & recent downloads (localStorage) |
| `run-tests.sh` | Local test runner |
| `run-e2e.sh` | Playwright E2E (app load, SSRF block; set `RUN_NETWORK_E2E=1` for CSV download) |
| `check_locales.py` | Locale key parity (de/en/ar) |
| `assets/icon.svg` | App icon |
| `.github/workflows/ci.yml` | CI on push/PR |

## Abhängigkeiten

- Python 3 (stdlib: `http.server`, json, csv, urllib)
- Optional: Kaggle CLI (auto-installed in `~/.cache/spickfolio/venv/`)
- Optional: `R` (für RData/RDS-Konvertierung)

## Tests

64 unit/integration tests + Playwright E2E. See `APP_CREATION_PLAYBOOK.md` for smoke checklist and roadmap status (slices A–AH complete).

```bash
./run-tests.sh
./run-e2e.sh
RUN_NETWORK_E2E=1 ./run-e2e.sh
```

Or manually:

```bash
python -m unittest test_server_security.py -v
python check_locales.py
```

## Lizenz

GPL-3
