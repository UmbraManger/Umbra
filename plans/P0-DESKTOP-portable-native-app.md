# P0-DESKTOP — Make Obscura a genuinely portable desktop app (no browser)

**Severity:** High · **Effort:** Medium · **Depends on:** run P0-repo-hygiene first

**Stated user requirement (verbatim intent):** *"I want this project to be like Cline
software — able to install or use portable — and NOT open in a browser for using this
software."*

This plan replaces the "make it a desktop app" framing with the real one. **Obscura is
already a desktop app** — the premise is half-satisfied, and the actual work is
repairing a packaging pipeline that does not currently work. Read the finding below
before assuming a rewrite is needed.

> **Status (reconciled 2026-10-05, HEAD `147f909`):** Steps 1, 2, 3, 4 and 6 are
> **already implemented in the working tree** — verified, not assumed:
> spec moved to `backend/Obscura.spec` (paths fixed, `pydantic`/`cloudscraper` in
> `hiddenimports`, `../scrapers` bundled), `build.bat` exists and produced
> `backend\dist\Obscura\Obscura.exe` (`build.log` ends "Build complete!"), `main.py`
> wraps startup in `db.alert(...)`, `db.app_dir()` has the `_writable()` →
> `%LOCALAPPDATA%\Obscura` fallback, `scrapers.install_bundled()` ships the library into
> the portable app, `README.md` exists. Step 5 (tkinter → pywebview native dialogs) is
> **still open** and is optional.
> **What is NOT done are this plan's done criteria 2, 3 and 4** (run from a copied
> folder / fails legibly / recreates `data\`) — nobody has executed them. Do those before
> marking this DONE; do not redo the build work above. Also note done criterion 5's test
> count is stale: the suite is now **90 tests, 5 skipped** (a `tests/test_julesjordan.py`
> was added), so the gate is "still 90, still OK", not "87".


---

## Finding 1 — It already launches a native window (good news)

`backend/main.py:19-47`:

```python
if "--browser" in sys.argv:
    import webbrowser
    webbrowser.open(url + f"/?t={API_TOKEN}")
    ...
else:
    import webview
    webview.create_window("Obscura", url + f"/?t={API_TOKEN}",
                          width=1360, height=860, min_size=(960, 640))
    webview.start()
```

The **default** path is `webview.create_window` — a real native OS window via pywebview
(WebView2 on Windows). The browser is opt-in behind an explicit `--browser` flag. So
the "don't open a browser" requirement is **already met** by default.

pywebview 6.2.1 is installed, and this machine has **Microsoft Edge WebView2 Runtime
154.0.4258.53** present — the backend pywebview needs. Verified, not assumed.

So the user's wish is *mostly already true*. The problem is everything around it.

## Finding 2 — The PyInstaller spec cannot possibly work (CRITICAL)

`Obscura.spec` sits at the **repo root**, but:

## Finding 3 — Hidden imports are incomplete for a frozen build

`server.py` imports at module scope: `db, crypto, keystore, backup, scrapers, scanner,
media, cloudscraper, requests, yaml` (via scrapers), `pydantic`, `fastapi`,
`starlette`, `uvicorn`, `python-multipart`.

The spec's `hiddenimports` covers most of these but **misses**:

- `pydantic` — imported directly by `server.py`; FastAPI's own models depend on it
- `cloudscraper` — imported directly by `server.py:12`; it dynamically imports
  `requests`-adjacent internals and ships its own `user_agent/browsers.json` data file
- `bs4`/`yaml` data files and `scrapers/*.py` — the bundled app cannot reach the
  `scrapers/` directory at all (see Finding 4)

Any one of these produces a frozen binary that starts, shows a window, then 500s on the
first scraper or AI call — a class of bug that is miserable to diagnose from a spec.

## Finding 4 — The frozen build has no `scrapers/` and no writable `data/`

Two runtime paths break once frozen:

1. **`scrapers/`** — `scrapers.py` reads `db.SCRAPER_DIR` (= `data/scrapers`) and the
   project ships 24 scraper modules in `<repo>/scrapers/`. The spec bundles only
   `frontend`. In a frozen build those modules are absent, so every scraper fails.
2. **`data/` location** — `db.app_dir()` (`db.py:22-25`) returns
   `dirname(sys.executable)` when frozen, so `data/` lands next to `Obscura.exe`. That
   is correct and genuinely portable — **but only if the user can write next to the
   exe.** Copy the app into `C:\Program Files\` and it fails with a permission error,
   with no fallback and no error message. `Obscura.spec` also sets `console=False`, so
   the user sees **nothing** — no window, no error, no traceback.

**This is the single most important thing to fix.** A portable app that dies silently
in a folder the user chose is worse than no app.

## Finding 5 — Native dialogs use tkinter inside a pywebview app

`server.py:358-386` opens folder/file pickers with `tkinter.filedialog`, creating a
**separate** `tk.Tk()` root window from inside the WebView2 window. These are different
toolkits; the dialog can appear behind the main window, on the wrong DPI, or with a
mismatched theme. Both functions already swallow every exception and return
`{"path": ""}` — so a failure is a dialog that silently never appears.

tkinter works here (verified: tkinter 8.6 present, and it is in `hiddenimports`), so
this is not broken — but it is the weakest part of the desktop experience.

---

## Steps

### Step 1 — Fix `Obscura.spec` and prove a build works end to end

**This is the whole ballgame.** A build script that produces a launchable `.exe` is the
single highest-value change in this plan.

Move the spec to `backend/Obscura.spec` so its paths resolve against `backend/`, or
keep it at root and fix every path. Moving it is cleaner — `frontend/` then needs
`('../frontend', 'frontend')`.

Corrected essentials:

```python
a = Analysis(
    ['main.py'],                 # now resolves: spec lives in backend/
    pathex=['.'],
    datas=[
        ('../frontend', 'frontend'),
        # ship the scraper library INSIDE the bundle — see Step 2
    ],
    hiddenimports=[
        ... existing entries ...,
        'pydantic', 'cloudscraper', 'cloudscraper.user_agent',
        'algolia', 'p1api', 'scrape', 'keystore',
    ],
    noarchive=False)
```

Add `pydantic` and `cloudscraper` — both are directly imported by `server.py` and
neither is currently listed.

### Step 3 — Fix the silent-failure mode (highest user impact)

`console=False` plus an unwritable `data/` equals an invisible crash. Two changes:

1. **Wrap `main()` startup in `backend/main.py` so any failure shows a message box**
   rather than exiting silently. Use `ctypes.windll.user32.MessageBoxW` — no new
   dependency, and it works before any UI exists. This single change converts the worst
   failure mode into a legible one.
2. **Make `data/` location robust.** Keep "next to the exe" (it is the portable
   behaviour you want), but if that directory is not writable, fall back to
   `%LOCALAPPDATA%\Obscura\` and tell the user where the library went. Do **not** fail.

Note this changes where `db.app_dir()` (`db.py:22-25`) points, so it interacts with P5
(wipe residue) and the backup paths. Make the fallback a single helper both use.

### Step 4 — Make the browser escape hatch explicit and hard to hit

The requirement is "not opening in a browser." It already only happens behind
`--browser`. Tighten it so it cannot happen by accident:

- Keep `--browser` (it is genuinely useful for debugging a desktop UI problem).
- Make the flag's help text explicit: `python main.py --browser  # debug only`.
- **Do not** remove the browser server. The whole frontend is served over
  `http://127.0.0.1:<port>` and pywebview points at that URL. Removing HTTP would mean
  rewriting the frontend transport — far beyond this plan.

### Step 5 — Replace the tkinter dialogs with native ones (optional, do last)

pywebview exposes native file dialogs. Prefer, in order:

1. **A pywebview JS bridge** — `window.pywebview.api` calling a `@js_api` method. This
   is the correct long-term fix and gives a real native dialog.
2. **Keep tkinter** if the bridge proves troublesome, but at minimum stop swallowing
   the exception silently — log it via `logging.getLogger("obscura")` (the convention
   `PATCHES.md` already establishes) so a broken dialog is diagnosable.

Only do this after the build works. A working app with an imperfect folder picker beats
a perfect one that will not launch.

### Step 6 — Write the portable-app README

There is currently **no README at all** in this repo. Write `README.md` covering:

- How to build: `build.bat`
- What the artifact is: `dist/Obscura/Obscura.exe` **plus the whole folder** — the exe
  alone will not run
- How to move it: copy the folder to a USB stick, run it, `data/` is created beside it
- Where the library lives: `data/` next to the exe
- How to back up: `GET /api/backup/export`, and where snapshots go
- The `--browser` debug flag
- The WebView2 requirement, and what to do if the app shows nothing (Step 3)

---

## Done criteria

Run these in order. **Do not declare this done until the second one passes on a
different machine or a different path.**

```bat
cd /d "C:\Users\Devin Bolivar\Downloads\Video\Obscura"
build.bat
```

1. **Builds clean** — `backend\dist\Obscura\Obscura.exe` exists; no missing-module
   warnings for `pydantic` or `cloudscraper`.
2. **Runs from a copied folder** — copy `dist\Obscura\` to `%TEMP%\obscura-portable\`,
   run `Obscura.exe` **from there**, confirm a native window opens (no browser), the
   library loads, and **a scraper actually returns results**. This is the real test: it
   exercises Finding 3 and Finding 4 together.
3. **Fails legibly** — run it from a read-only location (or a folder under
   `C:\Program Files\`) and confirm you get a message box, not silence.
4. **Creates its own data** — delete `data/` in the copy, relaunch, confirm it is
   recreated beside the exe.
5. **Regression gate** — the Python suite still passes:
   ```bat
   .venv\Scripts\python.exe -m unittest discover -s tests -t .
   ```
   The build changes no runtime logic, so the count must stay at 87.

## Files touched

- `Obscura.spec` — move to `backend/`, fix paths, add `pydantic` + `cloudscraper`
- `build.bat` — **new**; no build script exists today
- `backend/main.py` — startup error handling; clarify `--browser`
- `backend/db.py` — writable-`data/` fallback in `app_dir()`
- `backend/scrapers.py` — only if bundling scrapers (Step 2)
- `backend/server.py` — only if replacing tkinter dialogs (Step 5)
- `README.md` — **new**; none exists
- **No changes** to `backend/server.py` API behaviour, `crypto.py`, or the frontend

## Maintenance note

After this lands, **the spec and `build.bat` are load-bearing** — a dependency added to
`server.py` without a matching `hiddenimports` entry produces a broken release that
still builds. When adding an import to `backend/server.py`, check the spec. Better
still, once P0-repo-hygiene has committed everything, add a CI job that runs
`build.bat` so a broken spec fails loudly instead of at release time.

Note the interaction with `PATCHES.md`: it claims the `js/` modules "must ship next to
`index.html`" or the app shows an "App Did Not Finish Loading" toast. That warning
becomes a real packaging failure mode once frozen — if `datas` is wrong, the window
opens and is dead. Step 1's `frontend` entry is what prevents it, and done-criterion 2
is what proves it.

## Escape hatch

If a full frozen build proves unworkable in the time available — pywebview + PyInstaller
on Windows is a known-fiddly combination — **do not fake it**. Ship instead:

- A verified `run-portable.bat` that creates/uses a local venv, installs pinned deps
  from `requirements.lock.txt` (P0 Step 7), and launches `python backend/main.py`.
  That is genuinely portable in the sense the user cares about — no browser, no manual
  Python setup for the end user — and it is honest about being a script rather than an
  `.exe`.

Report back which route was taken and what blocked the other. Do not ship a spec that
has never been run and call the app portable.
Then create `build.bat` at the repo root (none exists today):

```bat
@echo off
setlocal
cd /d "%~dp0backend"
if not exist "..\.venv\Scripts\python.exe" (
  echo No venv. Create one and: pip install -r ..\requirements-dev.txt pyinstaller
  exit /b 1
)
"..\.venv\Scripts\python.exe" -m PyInstaller Obscura.spec --noconfirm --clean
if errorlevel 1 exit /b 1
echo.
echo Built: backend\dist\Obscura\Obscura.exe
echo Test it: copy that WHOLE Obscura folder elsewhere and run it.
```

The `COLLECT` (not `EXE`-only) form in the existing spec already produces a **folder**
distribution — that is exactly right for portability. Keep it.

### Step 2 — Bundle `scrapers/`, or make the app find it beside itself

Pick one, deliberately:

- **Option A (recommended):** add the scraper modules to `datas` so they ship inside
  the bundle. Simplest for the user: one folder, everything works.
- **Option B:** look for `scrapers/` next to `Obscura.exe` at runtime and document
  "copy your scrapers here". More flexible, worse UX.

If you take Option A, update `scrapers.py`'s module resolution so a frozen build finds
them — `db.SCRAPER_DIR` points at `data/scrapers` (user-installed), which is a
*different* thing from the project's `scrapers/` library. **Read how
`scraper_engine.run_by_id` resolves paths before changing this**; getting it wrong
means user-installed scrapers and bundled scrapers collide.
- `Analysis(['main.py'], ...)` — `main.py` is at `backend/main.py`. **`Test-Path
  .\main.py` returns `False`.** PyInstaller would fail immediately.
- `pathex=['.']` — resolves relative to the spec's directory (root), so it would not
  find `backend/` either.
- `datas=[('frontend', 'frontend')]` — `frontend/` *is* at root, so this one happens to
  be right, but the mismatch with `main.py` proves the spec was written assuming a
  different layout and never re-validated after `backend/` was introduced.

**This spec has never been successfully run.** There is no build script anywhere in the
repo (confirmed: no `build*` file at any level outside `.venv`), no CI, and no
`dist/` — so there is no artifact and no evidence it ever worked.