# Phase 0 - safety net (no application code was changed)

Phase 0 adds three things around the existing app and changes **none** of it:

1. **A verified snapshot of your data** (`tools/snapshot_data.py`)
2. **A git baseline** so every later fix is a reviewable diff you can roll back
3. **A test suite (82 tests)** that pins down today's behaviour, plus **16 "known bug" tests**
   that document each defect from the code analysis. They pass now as *expected failures*
   and turn red the moment a fix lands - that is your cue to delete the marker.

## Do this once (Windows, from the project folder)

```bat
:: 0. drop the contents of this zip into the project root (next to backend\ and frontend\)

:: 1. snapshot your real library BEFORE touching anything (safe while the app is open)
tools\snapshot_data.bat
::    -> backups\data-YYYYmmdd-HHMMSS\   (copy that folder somewhere off this disk too)

:: 2. git baseline
git init
git add -A
git commit -m "Baseline before fixes"
git tag baseline-pre-fix
::    .gitignore already excludes data\, backups\ and *.db - never commit your library.

:: 3. run the tests (needs nothing but Python; server tests need the packages below)
tools\run_tests.bat

:: 4. optional: also run the HTTP tests
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
tools\run_tests.bat
```

Expected result of step 3 without extra packages: `OK (skipped=12, expected failures=14)`.
With the packages installed: `OK (expected failures=16)`, nothing skipped.

If `data\` is not at `backend\data`, pass it: `tools\snapshot_data.bat --data "D:\path\to\data"`.

## How the tests keep your data safe

Every storage test runs in a throw-away temp folder: `tests/helpers.py` re-points
`db`, `crypto`, `scanner` and `scrapers` paths before each test and restores them after.
The real `data/` folder is never opened. The OS keyring is never touched either.

`known_bug` = `unittest.expectedFailure`. To see the real failure text for each one:

```bat
tools\show_known_bugs.bat
```

## Bug ledger - which test proves which finding

| Test (file) | What it proves | Analysis | Fix in |
|---|---|---|---|
| `test_db` deadlock after `close()` | `query/one/execute` take `_lock` then `connect()` takes it again. **Worse than first reported:** the very first call before `connect()` also deadlocks (the test base class must pre-connect, as `server.py` does at import) | #1 | Phase 3 |
| `test_crypto` failed re-key | Interrupted re-key leaves images under the new key but meta on the old one -> **data loss** | #2 | Phase 3 |
| `test_backup` restore keeps vault unlocked | `crypto._state` survives a restore | #3 | Phase 3 |
| `test_backup` directory entry in zip | Restore crashes **after** the live DB was already replaced | #3 | Phase 3 |
| `test_backup` API key inside `obscura.db` copy | `settings.json` is scrubbed but the DB copy carries the key | #5 | Phase 2 |
| `test_backup` restore enables `pyScrapers` | Restoring someone's backup can switch on code execution | #4 | Phase 2 |
| `test_scrapers` meta.json traversal | `remove()` deletes `../victim` from a crafted `meta.json` | #4 | Phase 2 |
| `test_media` file outside scan folders | Any stored path can be streamed | #1 | Phase 2 |
| `test_media` `.html` served as `text/html` | Non-video imports are served as web pages | #1 | Phase 2 |
| `test_server` delete fails open with no scan folders | Any stored path can be deleted | #7 | Phase 2 |
| `test_server` `PUT` can repoint `filePath` | Register-then-stream any file. **Fix must ignore the field, not reject it** - the frontend sends whole items on update | #1 | Phase 2 |
| `test_scanner` back cover sorts before front | Wrong image becomes the poster | Phase 4 | Phase 4 |
| `test_scanner` `Don'T` | `str.title()` | Phase 4 | Phase 4 |
| `test_media` short stem matches `banana.srt` | substring match | Phase 4 | Phase 4 |
| `test_media` `.vtt` gets a 2nd header | double `WEBVTT` | Phase 4 | Phase 4 |
| `test_scrapers` `ex.com` matches `apex.com.py` | substring host match | Phase 4 | Phase 4 |

## Not covered by tests yet (needs a JS test setup or a server; each gets a test in the phase that fixes it)

* XSS via `<img src="${item.photo}">` (`detail.js:422`) - Phase 2, needs a small DOM test
* App lock never engaging on backend start (`boot.js` / `sync.js`) - Phase 1
* "Clear all" not persisted (`deleteAll` -> `PUT` with `{}`), client ID collisions,
  fire-and-forget `Sync.push` - Phase 3
* `_safe_image_url` redirect/DNS-rebinding bypass, `run_yaml` SSRF - Phase 2 (`net_guard`)
* `/api/wipe` leaving `obscura.db.prev`, free pages and `posters/` - Phase 3
* `restore` blocking the event loop - Phase 3

## Rules for the next phases

1. Snapshot (`tools\snapshot_data.bat`) before running any fixed build against real data.
2. One fix = one commit. When a `known_bug` test starts passing the suite goes red
   ("unexpected success"): delete that decorator in the same commit.
3. Phase 1 changes the auth model (cookie instead of URL token), so `test_server.py`
   `SecurityTests` will be updated deliberately in that phase.
