# stats-sheets — Application Playbook

> Living engineering guide for **Statistisches Referenz-Desk** (stats-sheets).
> Use this file to pick up work, avoid regressions, and keep docs aligned with code.
> Update it whenever behavior, scope, or known limits change.

---

## 0) What this app is

A **single-user Linux desktop app** (local web UI + Python server) that combines:

1. **Cheat sheet** — R/Python stat snippets (copy to clipboard)
2. **Dataset browser** — search Rdatasets, Hugging Face, and Kaggle; preview; download as CSV/JSON/RData/RDS

**Stack:** vanilla HTML/CSS/JS frontend served by Python 3 `http.server`, opened in any browser. Optional Hyprland/Waybar integration.

**Not in scope:** multi-user hosting, auth, databases, Windows/macOS packaging, container orchestration, cloud deployment.

---

## 1) Current snapshot (2026-06-10)

| Area | Status | Notes |
|------|--------|-------|
| Cheat sheet tab | **Implemented** | JSON-driven cards, search filter, copy-to-clipboard |
| Dataset search (Rdatasets) | **Implemented** | Local cache at `~/.cache/stats-sheets/rdatasets.csv`, 1-day TTL auto-refresh |
| Dataset search (Hugging Face) | **Implemented** | Live API, max 100 results per query |
| Dataset search (Kaggle) | **Partial** | Requires `~/.kaggle/kaggle.json` or `access_token`; venv Kaggle CLI in cache dir |
| Dataset preview | **Implemented** | CSV/JSON/TSV; Parquet when pyarrow/pandas available |
| Dataset download | **Implemented** | Async jobs, queue persistence, paginated history, per-source path/format |
| Integration code snippets | **Implemented** | R/Python load code per dataset |
| i18n (DE / EN / AR) | **Implemented** | RTL for Arabic; keys in `de.json`, `en.json`, `ar.json` |
| Theme (dark / light) | **Implemented** | Cycles dark → light → system; follows `prefers-color-scheme` in system mode |
| Hyprland / Waybar integration | **Implemented** (optional) | `toggle-stats-sheets.sh` — not required on other DEs |
| Desktop app launcher | **Implemented** | `launch-stats-sheets.sh` + `install-desktop-entry.sh` |
| Heartbeat lifecycle | **Implemented** | Frontend pings every 10s; server exits after 30s silence |
| Rate limiting | **Implemented** | 30 req/min/IP (excludes `/heartbeat`, `/config`, `/download/status`) |
| Automated tests | **Implemented** | `test_server_security.py` — URL/path validation |
| Git repository | **Implemented** | https://github.com/Karim-Termanini/stats-sheets (private) |
| Module split | **Implemented** | `stats_sheets/` backend package; frontend in `js/*.js` (8 modules) |

---

## 2) Architecture

```
App menu / launch-stats-sheets.sh
    → python server.py          (127.0.0.1:18700 or dynamic port)
    → browser --app=http://127.0.0.1:PORT/
        → js/*.js  ←same-origin→  server.py
            → Rdatasets cache / HF API / Kaggle CLI / filesystem / Rscript

Optional (Hyprland): toggle-stats-sheets.sh + Waybar + window class stats-overlay
```

### Trust boundaries

| Context | Runs where | Can do |
|---------|------------|--------|
| **Frontend** | Chromium (`file://`) | UI, fetch to localhost API, clipboard |
| **Backend** | User Python process on `127.0.0.1` | Outbound HTTP (validated), subprocess (kaggle, Rscript, pip), write to user-chosen dirs |
| **Toggle script** | Bash / Hyprland | Start/stop server, open/close window |

### Sensitive operations

| Operation | Guard |
|-----------|-------|
| Outbound URL fetch (preview/download) | `validate_url()` — blocks localhost, private IPs, `.local` |
| File write (`/download`) | Denied prefixes (`/etc`, `~/.ssh`, `~/.kaggle`, …); dir must exist and be writable |
| Kaggle download | `kaggle:` URL scheme bypasses HTTP validation; uses isolated venv CLI |
| pyarrow install | `POST /install_pyarrow` runs `pip install pyarrow` in server Python |
| Shell commands | Use list args (`subprocess.run([...])`), not `shell=True` |

---

## 3) Project layout

| File | Purpose |
|------|---------|
| `index.html` | Shell UI: header, tabs, dataset views, banners |
| `js/storage.js` | Favorites & recent downloads (localStorage) |
| `js/state.js` | Shared app state, search cache |
| `js/api.js` | Server connection, pyarrow install, heartbeat |
| `js/i18n.js` | Translation loading and language switch |
| `js/cheat-sheet.js` | Cheat sheet load/render/filter |
| `js/datasets.js` | Dataset search, list, detail, favorites UI |
| `js/ui.js` | DOM refs, toast, clipboard, tabs |
| `js/main.js` | Bootstrap and launch-mode UI |
| `js/onboarding.js` | First-launch banner and dataset empty states |
| `js/keyboard.js` | In-app keyboard navigation and shortcuts |
| `server.py` | HTTP API, Rdatasets cache, external fetches, download/conversion |
| `styles.css` | Catppuccin theme, RTL, responsive grid |
| `cheat-sheet-data.json` | Cheat card structure + R/Python code blocks |
| `de.json` / `en.json` / `ar.json` | UI strings (cheat titles use i18n keys) |
| `launch-stats-sheets.sh` | Main launcher (any Linux DE) |
| `install-desktop-entry.sh` | App menu `.desktop` entry |
| `install-global-shortcut.sh` | Global Super+Shift+S shortcut (Hyprland/GNOME) |
| `toggle-stats-sheets.sh` | Optional Hyprland/Waybar toggle |
| `README.md` | User-facing setup (Hyprland, Waybar) |
| `~/.cache/stats-sheets/` | Runtime cache: `port`, `rdatasets.csv`, `venv/` (Kaggle CLI) |

**Ignored / not committed:** `venv/`, `__pycache__/`, `rdatasets.csv` (local copy), `.cache/`

---

## 4) Runtime

### Start (normal)

```bash
/home/karimorachy/Projects/stats-sheets/launch-stats-sheets.sh
```

Or from the application menu after `./install-desktop-entry.sh`.

Optional Hyprland: Waybar → `toggle-stats-sheets.sh` (see README).

### Manual dev

```bash
python /home/karimorachy/Projects/stats-sheets/server.py
# Open http://127.0.0.1:PORT/ in browser (port in ~/.cache/stats-sheets/port)
```

### Stop

- Click Waybar toggle again (closes window + stops server via PID file)
- Press **Esc** in overlay (closes window; heartbeat stops server within ~30s)

### Optional dependencies

| Tool | Used for | Detection |
|------|----------|-----------|
| `R` / `Rscript` | RData/RDS export | `/config` → `r_available` |
| `pyarrow` or `pandas` | Parquet preview/conversion | `/config` → `parquet_available` |
| Kaggle token | Kaggle search/download | `~/.kaggle/kaggle.json` or `access_token` |
| `xdg-user-dir` | Default Downloads/Documents paths | Fallback to `~/Downloads` |

---

## 5) HTTP API contract

Base: `http://127.0.0.1:{port}` — port from `~/.cache/stats-sheets/port` or `?port=` query param.

**CORS:** Allowed origins: `file://`, empty, `null`, any `localhost` / `127.0.0.1`.

### GET

| Path | Params | Response |
|------|--------|----------|
| `/config` | — | `{ r_available, parquet_available, kaggle_auth, downloads_dir, documents_dir, rdatasets_cached_at }` |
| `/heartbeat` | — | `{ ok: true }` |
| `/cheat-sheet` | — | cheat-sheet JSON array |
| `/translations` | `lang=de\|en\|ar` | locale JSON object |
| `/search` | `q`, `source=all\|rdatasets\|huggingface\|kaggle`, `page`, `per_page` | `{ results, totals, pagination, kaggle_skipped?, needs_auth? }` |
| `/preview` | `url` | `{ rows, columns }` or `{ error }` |
| `/hf_files` | `dataset_id` | HF file list for dataset picker |
| `/url_size` | `url` | `{ size }` or error |
| `/download/status` | `job_id` | job status `{ phase, bytes_read, bytes_total, done, error?, file_path?, message? }` |

### POST

| Path | Body | Response |
|------|------|----------|
| `/download` | `{ url, dataset_name, format, target_dir }` | `{ job_id }` — poll `/download/status` until `done` |
| `/download/cancel` | `{ job_id }` | `{ ok: true }` — cooperative cancel for active job |
| `/open_path` | `{ path, action?: folder\|file }` | `{ ok: true }` — `folder` reveals dir; `file` opens with default app |
| `/notify` | `{ title, body }` | `{ ok: true }` or `{ error_code: notify_* }` |
| `/install_pyarrow` | — | `{ success, parquet_available }` or `{ error_code: pyarrow_install_* }` |
| `/refresh_rdatasets` | — | `{ success, count, cached_at }` or `{ error_code: rdatasets_refresh_failed }` |
| `/kaggle/open_credentials_dir` | — | `{ ok: true, path }` — creates `~/.kaggle` if needed and opens it |

**Error shape:** `{ "error_code": "stable_key", "error": "optional legacy message" }` with HTTP 4xx/5xx. Frontend resolves `error_code` via locale keys.

**Success shape:** varies by endpoint; frontend should check `error` field before treating as success.

---

## 6) Feature maturity labels

Use only these in docs and this playbook:

- **Implemented** — works in normal use on target platform
- **Partial** — works with setup gaps or known limits
- **Planned** — not built yet

Never describe Planned items as done in README or UI.

---

## 7) Known technical debt (prioritized)

1. ~~**Monolith files**~~ — backend split into `stats_sheets/`; frontend split into `js/*.js`.
2. ~~**No git**~~ — done; repo at Karim-Termanini/stats-sheets.
3. ~~**No tests**~~ — `test_server_security.py` covers URL/path helpers; expand as needed.
4. ~~**`pkill -f`**~~ — replaced with PID file at `~/.cache/stats-sheets/server.pid`.
5. ~~**Google Fonts CDN**~~ — removed; system font stack, fully offline UI.
6. ~~**README typo**~~ — fixed.
7. **Locale parity** — run `python check_locales.py` after editing locale files.
8. **Project `venv/`** — local dev artifact; runtime Kaggle venv lives in `~/.cache/stats-sheets/venv`.

---

## 8) Quality gate (before expanding scope)

Minimum bar before adding new features:

- [ ] Manual smoke pass (see §9) passes
- [ ] README and this playbook status tables match code
- [ ] No secrets in tracked files
- [ ] Locale keys added to all three JSON files when UI strings change

Stretch goals:

- [x] Git initialized; `.gitignore` respected
- [x] `python -m unittest` smoke tests for `validate_url` and path denial
- [x] Locale key parity script (`check_locales.py`)

---

## 9) Manual smoke checklist

Run after non-trivial changes:

1. **Launch** — Waybar toggle opens overlay centered, correct size (Hyprland rules).
2. **Server** — Toast does not show connection error; `/config` values populate banners correctly.
3. **Cheat sheet** — Search filters cards; click copies code; toast appears.
4. **Language** — Switch DE → EN → AR; RTL applies for AR; no missing-key raw strings; **select dropdown options are readable** in both themes.
5. **Rdatasets** — Search returns results; detail view opens; preview works for a CSV dataset.
6. **Download** — CSV to chosen folder succeeds; **download-complete modal stays open** until dismissed; Open file / Show in folder work.
7. **Download queue** — Queue an item, reload app; pending queue restores and resumes when server connects.
8. **Download history** — Filter by name/path; pagination moves through stored entries.
9. **HF** — Search returns results (network required).
10. **Kaggle** — With token: search works; sizes show as MB/GB not raw bytes. Without: setup banner shows **Open API settings**, **Open ~/.kaggle folder**, and **Check again**.
11. **Kaggle preview** — Large datasets (>50 MB) show preview disabled with localized message, not a timeout.
12. **Esc / toggle** — Window closes; server process stops (check `pgrep -f server.py`).
13. **Heartbeat** — Close window without toggle; server exits within ~30s.

---

## 10) Testing strategy (this stack)

No Vitest/Tauri/Rust. Appropriate tools:

| Layer | Tool | Target |
|-------|------|--------|
| Python unit | `unittest` / `pytest` | `validate_url`, path checks, CSV parsing helpers |
| Python integration | `unittest` + `http.client` | `/config`, `/search` with mocked cache |
| Shell | manual or `bats` | `toggle-stats-sheets.sh` idempotency |
| Frontend | manual smoke | DOM rendering, tab switch, keyboard nav |
| E2E | optional Playwright against `file://` + live server | One happy-path download |

**Test what breaks first:**

- SSRF validation edge cases (private IP, redirect — if added later)
- Download to denied paths
- Malformed JSON POST bodies
- Rate limit 429 responses
- Missing Kaggle auth / missing R / missing pyarrow fallbacks

---

## 11) Vertical slices

### Slice A — Cheat sheet (done)

- **Input:** open overlay, cheat tab, search, click code block
- **Output:** clipboard + toast
- **Evidence:** manual smoke §9 items 3–4

### Slice B — Rdatasets browse/preview/download (done)

- **Input:** datasets tab, filter Classic R, search, open detail, preview, download CSV
- **Output:** file in chosen directory
- **Evidence:** manual smoke §9 items 5–6

### Slice C — Multi-source search (done, Kaggle partial)

- **Input:** filter HF / Kaggle, paginate results
- **Output:** unified result list with source badges
- **Gap:** Kaggle requires user token setup

### Slice D — Stabilization (done)

- Git repo, unit tests, locale check, README fix, PID-based server stop, cross-distro launcher, CI workflow

### Slice E — Polish (done)

- Offline fonts, HF/Kaggle TTL caching, favorites/recents

### Slice F — Module split (done)

- `stats_sheets/` package: security, config, handler, main, …
- `server.py` → thin entry point
- `js/storage.js` for localStorage
- `run-tests.sh` for local CI

### Slice G — Frontend module split (done)

- Split monolithic `script.js` into `js/state.js`, `js/api.js`, `js/i18n.js`, `js/cheat-sheet.js`, `js/datasets.js`, `js/ui.js`, `js/main.js`
- `index.html` loads modules in dependency order; `static_files.py` serves all `/js/*.js` routes
- Removed `script.js`

### Slice H — Export recent downloads (done)

- **Export CSV** button on Recent tab; client-side download of all stored recent entries
- Columns: name, id, source, package, item, format, file_path, downloaded_at (ISO)
- Fixed missing `});` in `datasets.js` filter-pill listener

### Slice I — Dark/light theme toggle (done)

- Header toggle (☀/🌙); preference stored in `localStorage` (`app_theme`)
- Catppuccin-style dark (default) and light palettes via CSS custom properties on `html[data-theme]`
- Inline head script prevents flash of wrong theme on load

### Slice I+ — System theme sync (done)

- Third theme mode: **system** (default for new installs); follows OS `prefers-color-scheme`
- Toggle cycles dark → light → system; live updates when OS theme changes
- `data-theme-mode` on `<html>` drives icon; `data-theme="light"` sets effective palette

### Slice J — Theme keyboard shortcut (done)

- **Ctrl+Shift+T** cycles dark → light → system (skipped while typing in inputs)
- Toast confirms the active mode; theme button uses shared `cycleTheme()`

### Slice J+ — Keyboard navigation (done)

- New `js/keyboard.js`: roving tabindex, Home/End, PageUp/Down, pagination at list edges
- Filter pills: arrow keys + Enter; Esc exits detail view before closing window
- Global: Ctrl+1/2 tabs, `/` focus search, ↓ from search enters list
- ARIA listbox/option roles; focus restored when returning from detail

### Slice K — Cheat sheet keyboard navigation (done)

- Roving focus on `.copyable` code blocks; ↑↓←→, Home/End, Enter/Space to copy
- ↓ from search enters first visible snippet; focus ring and aria labels
- Re-inits tabindex after render and filter

### Slice K+ — Localized copy hint (done)

- Cheat sheet hover/focus tooltip uses `--copy-hint-text` CSS variable from locale `copyHint` key
- RTL positions hint on the left for Arabic

### Slice L — Onboarding and empty states (done)

- Dismissible first-launch banner (`localStorage`); quick-start tips for tabs and shortcuts
- Dataset empty states: SVG icon + title + contextual hint (search / favorites / recent)
- New module `js/onboarding.js`

### Slice L+ — Connection error empty state (done)

- `renderConnectionErrorState()` with warning icon, hint, and Retry button
- Startup failure shows error in cheat sheet grid and dataset list
- Dataset search failures retry the current query/page

### Slice M — Search HTTP error states (done)

- Search checks HTTP status before parsing results
- Distinct empty states: **429** rate limit (yellow), **5xx** server error, **4xx** client error, network failure
- Shared `renderHttpErrorState()` with retry per error type

### Slice M+ — Rate limit countdown (done)

- Server sends `Retry-After` on 429 (seconds until window clears)
- Retry button shows countdown (`Retry in 45s`) and stays disabled until zero

### Slice N — Kaggle setup guidance (done)

- `/config` exposes `kaggle_auth` (token file present)
- Step-by-step setup banner on Kaggle filter with **Check again** (re-reads config, re-runs search)

### Slice N+ — README sync (done)

- Features, Kaggle setup, keyboard/usage, project layout aligned with current app

### Slice O — Global launch shortcut (done)

- `install-global-shortcut.sh` — Super+Shift+S via Hyprland `hyprland.conf` or GNOME gsettings
- Hyprland uses `toggle-stats-sheets.sh`; other DEs use `launch-stats-sheets.sh`
- `--remove` uninstalls; manual steps printed for KDE/XFCE/i3

### Slice P — Search debounce and HF server cache (done)

- Source-aware debounce: 150 ms favorites/recent, 250 ms Rdatasets, 450 ms HF/Kaggle/all
- Server-side HF cache (`stats_sheets/hf_cache.py`, 5 min TTL, 64 entries)

### Slice Q — Dataset detail skeleton (done)

- Shimmer skeleton while detail panel loads; HF waits for `/hf_files` before render
- Stale-response guard when switching datasets quickly

### Slice R — Preview table skeleton (done)

- Shimmer grid while `/preview` loads; stale-response guard on close/reclick

### Slice S — Download progress (done)

- Async download jobs (`download_jobs.py`, `download_service.py`); `POST /download` returns `job_id`
- `GET /download/status?job_id=` polled by frontend; progress bar with byte counts or indeterminate mode

### Slice T — Download cancel, ETA, retry (done)

- `POST /download/cancel` with cooperative cancel during HTTP/Kaggle download
- ETA from byte rate when `Content-Length` known
- Cancel and Retry buttons in progress UI; error state keeps retry visible

### Slice U — Download queue, notify, show-in-folder (done)

- FIFO download queue with global status bar; additional clicks enqueue while one runs
- `POST /open_path` + **Show in folder** button after success (`xdg-open` on parent directory)
- `POST /notify` when download completes and browser tab is hidden (`notify-send`)

### Slice V — Open file, queue clear (done)

- `POST /open_path` `action: file` opens downloaded file via `xdg-open`; **Open file** button after single-file downloads
- **Clear queue** button on queue bar removes pending items
- **Project Folder** sets Documents path, toast feedback, and opens folder in file manager

### Slice W — History panel, queue reorder, open-on-complete (done)

- Collapsible **Download history** panel (last 10 entries, show folder / open file)
- Queue list with move up/down and remove per pending item
- **After download** preference: do nothing, open folder, or open file (localStorage)

### Slice X — History filter, queue drag, per-source paths (done)

- History panel search filters all stored recents by name, path, source, package
- Queue items reorder via drag handle (⠿); ↑↓ buttons remain
- Target folder remembered per source (`rdatasets`, `huggingface`, `kaggle`) in localStorage

### Slice Y — History pagination, queue persistence, format per source (done)

- History panel pages through filtered results (10 per page)
- Pending download queue restored from localStorage and resumes when server connects
- Export format remembered per source (`csv` / `json` / `rdata` / `rds`)

### Slice Z — Smoke checklist, tests, Kaggle setup polish (done)

- Manual smoke checklist §9 updated for modal, queue/history, dropdown contrast, Kaggle size/preview
- Backend tests for Kaggle preview limits, auth detection, credentials dir creation
- Kaggle setup banner: link to API settings, open/create `~/.kaggle` folder button

### Slice AA — Handler tests and localized download errors (done)

- Integration tests against live `Handler` (`/config`, `/preview`, `/download`, `/open_path`, translations)
- Download and open-path failures return stable `error_code` keys; frontend uses `resolveApiError()`
- Unit tests for `validate_download_request` and job `error_code` propagation

### Slice AB — SSRF error codes and Playwright E2E (done)

- `validate_url()` returns stable `url_*` error codes; handler and download validation use them
- Locale strings for all SSRF codes (DE/EN/AR)
- Playwright E2E: app load, SSRF block, optional networked CSV download (`RUN_NETWORK_E2E=1`)

### Slice AC — SSRF/rate-limit UI error codes (done)

- Preview and `/url_size` SSRF failures show localized `url_*` messages in the detail panel
- 429 responses return `error_code: rate_limit`; search/download use `parseJsonResponse` + locale keys

### Slice AD — parseJsonResponse rollout and rate-limit E2E (done)

- `hf_files` and `/config` fetches use `parseJsonResponse` for localized API errors
- Playwright E2E: dataset list shows `.empty-state-warn` after 429 search rate limit

### Slice AE — POST handler parseJsonResponse and rate-limit test reset (done)

- `open_path`, Kaggle credentials dir, `install_pyarrow`, and `refresh_rdatasets` use `parseJsonResponse`
- `reset_rate_limit_state()` clears rate-limit windows; integration tests reset in setUp/tearDown

### Slice AF — Download/notify parseJsonResponse and install error codes (done)

- Download POST, status poll, and `/notify` use `parseJsonResponse`
- `pyarrow_install_*`, `rdatasets_refresh_failed`, `notify_*`, and download cancel return `error_code`

### Slice AG — Ideas (planned)

- Localized `error_code` for remaining handler strings (invalid action, 404 endpoints)
- E2E: download validation error toast shows localized `url_*` message

---

## 12) Build sequence for continuing work

1. Read §1 status table and §7 debt list.
2. Pick one slice from §11; freeze other feature work.
3. If touching API: update §5 contract table in same change.
4. If touching UI strings: update all three locale files.
5. Run manual smoke §9.
6. Update §1 status and §7 debt in this playbook.
7. Commit one logical change at a time (when git exists).

---

## 13) Vertical slice template (copy for new work)

### A) Slice identity

- **Slice name:**
- **User value (one sentence):**
- **In-scope:**
- **Out-of-scope:**

### B) Safety

- **Touches filesystem?** yes/no
- **Touches network?** yes/no — which hosts
- **Subprocess?** yes/no — which commands
- **Failure classes:** connection | permission | not found | timeout | invalid

### C) Contract changes

- **New/changed endpoints:**
- **Request/response shapes:**

### D) Evidence required

- [ ] Manual smoke items listed
- [ ] §5 API table updated
- [ ] §1 status updated
- [ ] Locale files synced (if UI changed)

---

## 14) Platform constraints

**Target:** Any Linux desktop (GNOME, KDE, XFCE, Hyprland, etc.) with Python 3 and a browser.

Optional Hyprland setup in README:

- `windowrulev2` for class `stats-overlay` (float, center, 1050×750)
- Waybar module pointing at `toggle-stats-sheets.sh`

**Not supported:** Windows, macOS (untested).

---

## 15) Commit discipline

- One intent per commit: feature, fix, refactor, or docs — not mixed.
- Message: what changed and why.
- Do not commit `venv/`, `rdatasets.csv`, `__pycache__/`, or `~/.cache/` contents.
- Do not commit Kaggle credentials.

---

## 16) Incident log

Add an entry when something breaks in development.

### Template

- **Date:**
- **Area:** frontend | server | toggle | i18n | docs
- **Symptom:**
- **Root cause:**
- **Fix:**
- **Preventive rule:**
- **Status:** open | resolved

### Log

#### Monolith growth

- **Area:** architecture
- **Symptom:** `server.py` and monolithic frontend each exceeded 1000 lines; hard to navigate.
- **Root cause:** rapid feature addition without module extraction.
- **Fix:** backend → `stats_sheets/` package; frontend → `js/*.js` modules (Slice G).
- **Preventive rule:** new domains get a dedicated module once logic exceeds ~50 lines.
- **Status:** resolved

#### No git history

- **Area:** process
- **Symptom:** no version control in project directory.
- **Root cause:** never initialized.
- **Fix:** repo created at Karim-Termanini/stats-sheets.
- **Status:** resolved

#### README language typo

- **Area:** docs
- **Symptom:** `Ein浮es Overlay` in README line 3.
- **Root cause:** encoding/typo during bilingual write-up.
- **Fix:** corrected to `Ein schwebendes Overlay`.
- **Status:** resolved

---

## 17) Maintenance rule

When a bug or design lesson appears:

1. Add §16 incident entry.
2. Update §1 status or §7 debt if scope changed.
3. Update §5 if API changed.
4. Keep language factual — no roadmap marketed as shipped.

This file is the canonical engineering status alongside `README.md` (user setup only).
