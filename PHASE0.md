# Phase 0 - safety net (no application code was changed)

Phase 0 adds three things around the existing app and changes **none** of it:

1. **A verified snapshot of your data** (`tools/snapshot_data.py`)
2. **A git baseline** so every later fix is a reviewable diff you can roll back
3. **A test suite (102 tests)** that pins down today's behaviour, plus
   **16 "known bug" markers** that document each defect from the code analysis.
   They pass now as *expected failures* (`unittest.expectedFailure` in
   `tests/helpers.py`) and turn red the moment a fix lands - that is your cue
   to delete the marker in the same commit.

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
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
tools\run_tests.bat
```

Expected result of step 3: `Ran 102 tests in 8.328s` → `OK (skipped=5)`.
With the web packages installed, the same suite skips 0.

If `data\` is not at `backend\data`, pass it: `tools\snapshot_data.bat --data "D:\path\to\data"`.

## How the tests keep your data safe

Every storage test runs in a throw-away temp folder: `tests/helpers.py` re-points
`db`, `crypto`, `scanner` and `scrapers` paths before each test and restores them after.
The real `data/` folder is never opened. The OS keyring is never touched either.

`known_bug` = `unittest.expectedFailure`. To see the real failure text for each one:

```bat
tools\show_known_bugs.bat
```

## Phase 0 closed - what it was for

The 16 "known bug" markers caught, in order: `test_db` deadlock; `test_crypto`
interrupted re-key; `test_backup` restore keeps vault unlocked; `test_backup`
directory entry in zip; `test_backup` API key inside `obscura.db` copy;
`test_backup` restore enables `pyScrapers`; `test_scrapers` meta.json traversal;
`test_media` file outside scan folders; `test_media` `.html` served as
`text/html`; `test_server` delete fails open with no scan folders; `test_server`
`PUT` can repoint `filePath`; `test_scanner` back cover sorts before front;
`test_scanner` `Don'T`; `test_media` short stem matches `banana.srt`; `test_media`
`.vtt` gets a 2nd header; `test_scrapers` `ex.com` matches `apex.com.py`.

Each was fixed in the session documented in `PATCHES.md` (A1-A5, B, C) and the
fix is verified by the suite now passing it as a real test. The markers are
kept only as documentation of what was wrong - delete them in the same commit
as the fix.

## Open items - pointer to the phase plans

Every remaining item now has its own plan file in `plans/`:

| Plan | State |
|---|---|
| `plans/P3-app-lock-is-client-side.md` | Open - server-side lock, API 423 when locked (Option A chosen) |
| `plans/P4-restore-blocks-event-loop.md` | Open - `restore` blocks the event loop |
| `plans/P5-wipe-residue.md` | Open - `wipe` leaves db.prev / free pages / posters/ |
| `plans/P6-frontend-test-harness.md` | Open - frontend has zero automated tests |

## Rules for the next phases

1. Snapshot (`tools\snapshot_data.bat`) before running any fixed build against
   real data.
2. One fix = one commit. When a `known_bug` test starts passing the suite goes
   red ("unexpected success"): delete that decorator in the same commit.

