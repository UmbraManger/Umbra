# Obscura

A private, local-first media library manager that runs as a **native desktop app** —
no browser, no install, no cloud account. Python + FastAPI + SQLite behind a pywebview
window; your library is encrypted at rest and lives in a `data/` folder next to the app.

---

## Build

```bat
build.bat
```

It runs PyInstaller over `backend/Obscura.spec` and produces:

```
backend\dist\Obscura\Obscura.exe
```

> **The artifact is the WHOLE `dist\Obscura` folder, not just the exe.**
> Copying only `Obscura.exe` gives you a program that starts and then dies.
> (`_internal\` holds the frontend, the scraper library and the Python runtime.)

## Run it anywhere

1. Copy the entire `dist\Obscura` folder to a USB stick, an external drive, or any
   other Windows machine.
2. Run `Obscura.exe`.
3. On first run a `data\` folder is created **next to the exe**, and the app creates its
   encrypted library there. Nothing is written outside that folder.

There is no installer and nothing to uninstall — delete the folder.

### Requirement: Microsoft Edge WebView2 Runtime

The window is rendered by WebView2, the runtime Edge ships on Windows 10/11. It is
preinstalled on current Windows; if it is missing, install the **Evergreen Standalone
Installer** from Microsoft (free) and relaunch.

If you get **no window at all**: the app now shows a message box with the error instead
of dying silently — read it. If nothing at all appears, the most common cause is a
missing WebView2 runtime; the second is an antivirus quarantine.

## Where your library lives

```
<Obscura folder>\data\
├── obscura.db      SQLite database (catalogue, settings, scraper registry)
├── posters\        cached artwork
├── encrypted\      encrypted images
└── scrapers\       installed scrapers (bundled ones are installed on first run)
```

If the folder holding the exe is **not writable** (for example you dropped the app into
`C:\Program Files`), Obscura does not fail — it moves its data to
`%LOCALAPPDATA%\Obscura\data` and tells you so in a message box.

## Back up

- In-app: `GET /api/backup/export` downloads a full encrypted snapshot
  (`data/obscura.db`, posters and encrypted images).
- Restore with `POST /api/backup/restore` from the app (it is staged — a bad archive
  cannot half-apply).
- Manual backup: copy the whole `data\` folder with the app closed.
- The bundled scraper library also lives in the app folder (`_internal\scrapers`); it is
  re-installed into `data\scrapers` on every launch, so your own installed scrapers and
  their settings survive independently.

## `--browser` (debug only)

```bat
Obscura.exe --browser
```

Normally Obscura serves its UI to a **native pywebview window** pointed at
`http://127.0.0.1:<port>` — that local HTTP server is the transport, not a "browser
mode". `--browser` skips the native window and opens your normal browser instead; it
exists only for debugging a rendering problem. Leave it off for normal use.

Python scrapers also execute arbitrary local code, so they are disabled by default —
enable them in **Settings › External Scrapers › Python Scrapers** if you trust the
scraper.

## Development

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -t .
.venv\Scripts\python.exe backend\main.py             # native window
.venv\Scripts\python.exe backend\main.py --browser   # debug in a browser
```

**After changing imports in `backend/`**: if you added a third-party import to
`server.py`, add it to `hiddenimports` in `backend/Obscura.spec` too, or the frozen
build will build cleanly and then fail at runtime.