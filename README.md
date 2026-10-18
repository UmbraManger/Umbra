<p align="center"><img src="frontend/img/umbra.png" alt="Umbra" width="96"></p>

# Umbra

**A private, portable media library manager that runs as a native desktop app — no browser, no installer, no cloud account, no telemetry.**

Python + FastAPI + SQLite behind a pywebview window; a zero-framework JavaScript frontend; your library lives encrypted in a `data/` folder next to the exe.

`Version 1.1` · `License: GPL-3.0` · `Windows 10/11`

---

## Features

### Library
- **Movies, Scenes, Performers, Studios, Categories** — full CRUD with detail pages, related sections, and cast/category chips
- Search, filters (studio, cast, category, year/date ranges), **grid and list views**, adjustable card widths, pagination
- **Bulk actions** (select all / favorite / delete), favorites, **playlists**, favorites & quick stats on the Profile tab
- Folder **scanner** with ffprobe durations, duplicate detection, and "Mark Unimported" cleanup

### Playback
- **Custom internal player** — hover seek with thumbnails, skip ±10s, volume, subtitles/audio/quality menus, fullscreen, auto-hiding control bar, poster covers
- **Scene-chain playback** — a movie with no local file plays its linked scenes in sequence; Prev/Next live in the control bar as icons
- **Continue Watching** — progress rows on the Movies and Scenes tabs, sorted by most recently watched, with progress bars
- **Resume everywhere** — exact scene + second, including mid-scene offsets inside a chain; short watches count too
- **OS default player** mode — one click hands the file to your system player
- Thumbnail-based fallback player when the browser can't decode a codec

### Metadata
- **~25 bundled site scrapers** (Python) for info, covers, and galleries — disabled by default since they execute local code; enable per-trust in Settings
- **AI-assisted lookup** — OpenAI-compatible providers, including local models (Ollama) and Google Gemini
- Algolia and P1 search backends; sidecar subtitle loading (SRT → VTT); share dialogs with caption generation and bulk download

### Privacy & security
- **Local-first**: everything lives in `data/` next to the exe — portable to a USB stick
- **Encrypted at rest** — optional image protection (passphrase-keystore) for artwork galleries
- **App lock** — password on launch; the hash never leaves the server process
- Per-run API token + Host/Origin enforcement on every `/api/` route; media paths are containment-checked
- **No telemetry, no accounts, no cloud** unless you deliberately set up sync

### Quality of life
- Encrypted **backup export** and staged **restore** (a bad archive cannot half-apply)
- Dark/light themes, custom accent, frameless window with a drawn, theme-matched title bar
- Export the whole library as JSON; import-friendly schema migrations

---

## How it works

```
Umbra.exe  (PyInstaller bundle)
├─ FastAPI server on 127.0.0.1:<port>
│   ├─ SQLite               data/obscura.db — catalogue, settings, watch positions
│   ├─ media engine         streaming, ffprobe, sidecar subs, open/reveal in OS
│   ├─ scraper engine       bundled Python scrapers + AI metadata lookup
│   └─ crypto / keystore    encrypted images, app-lock hash, AI keys
├─ pywebview native window  renders frontend/ via the WebView2 runtime
└─ data/ folder             portable library; falls back to %LOCALAPPDATA%
```

The frontend is plain script-tag JavaScript — no build step, no npm runtime dependencies. It talks to the local server over HTTP with a per-run token. `--browser` skips the native window and opens a normal browser, for debugging only.

---

## Quickstart

### Build the portable app

```bat
build.bat
```

Produces `backend\dist\Umbra\Umbra.exe`. **The artifact is the whole `dist\Umbra` folder** — `_internal\` holds the frontend, scrapers and Python runtime. Copy the folder anywhere (USB stick included) and run; a `data\` folder is created next to the exe on first run.

Requires the **Microsoft Edge WebView2 Runtime** (preinstalled on current Windows; free standalone installer otherwise).

### Development

```bat
.venv\Scripts\python.exe backend\main.py             # native window
.venv\Scripts\python.exe backend\main.py --browser   # debug in a browser
```

### Tests

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -t .   # 127 backend tests
npm test                                                      # 35 frontend tests (jsdom)
```

Both suites are green on `master`.

> **After adding a third-party import to `backend/server.py`**: also add it to `hiddenimports` in the PyInstaller spec, or the frozen build succeeds and then dies at runtime.

---

## Your data

```
<data folder>/
├── obscura.db        SQLite catalogue, settings, scraper registry, watch positions
├── posters/          cached artwork
├── encrypted/        encrypted images
└── scrapers/         installed scrapers (bundled ones reinstall on launch)
```

- **Backup in-app**: `GET /api/backup/export` downloads an encrypted snapshot; restore with `POST /api/backup/restore` (staged, atomic).
- **Manual**: copy the whole `data\` folder with the app closed.
- If the app folder isn't writable (e.g. `C:\Program Files`), data moves to `%LOCALAPPDATA%\Umbra\data` and tells you so.

---

## Donate

Umbra is free and open source. If it saves you time, donations are welcome:

- **TON / GRAM**: `UQC3UZWZnH859-gvJ0a0U_h3C_1m-gDvFYTLeKIHxNdSluPs`
- **Tron / TRX**: `TSPYepCjZ3egvXSPMxkiDTcr2PNtjV7ohh`

---

## Disclaimer

Umbra is intended **for adults (18+)** and for organizing media you have the legal right to possess. Scrapers target third-party sites; you are responsible for complying with those sites' terms and the laws of your jurisdiction. The software comes without any warranty; see the license.

## License

[GPL-3.0](LICENSE) — you may use, study and share this software, and derivatives must remain open source under the same license.
