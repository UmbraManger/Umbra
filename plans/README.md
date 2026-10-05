# Obscura — audit findings & implementation plans

Audit date: 2026-10-05 · Branch: `master` · HEAD: `147f909` "Baseline before fixes"
· Last reconciled: 2026-10-05 (same HEAD; working-tree drift re-verified — see
Current state and the Status column).

## What this repo is

Obscura is a **local-first desktop media-library manager** (FastAPI + SQLite + pywebview,
vanilla-JS frontend, PyInstaller spec). It scans folders for media, scrapes metadata from
~25 sites, encrypts images at rest, and syncs state to a remote backend when configured.

## The project goal (user-stated, 2026-10-05)

> *"I want this project to be like Cline software — able to install or use portable —
> and NOT open in a browser for using this software."*

**Obscura is a portable desktop application.** It launches its own native OS window and
must never require the user to open a browser to use it. It must be runnable by
copying a folder to another machine (or a USB stick) and double-clicking.

This is a **standing product constraint**, not a one-off task. Any plan that conflicts
with it is wrong. Specifically:

- The default launch path must stay `webview.create_window` (`backend/main.py:44`).
  `--browser` is a **debug-only** escape hatch, never the default.
- The HTTP server on `127.0.0.1` stays — it is the transport pywebview points at, not
  a browser-usage path. Do not "fix" browser usage by tearing out the server.
- `data/` must live **beside the executable** so a copied folder carries its library.
- Shipping a working frozen build (`build.bat` → `dist/Obscura/`) is part of "done",
  not a future nicety.

The full plan is [P0-DESKTOP](P0-DESKTOP-portable-native-app.md).

---

## Current state (verified, not assumed — re-checked 2026-10-05, HEAD `147f909`)

| Fact | Evidence |
|---|---|
| Single commit; entire fix corpus still **uncommitted** | `git log` → 1 commit; unstaged 32 files +1290/−743, staged 14 files +520/−1596 |
| Test suite **passes** | `python -m unittest discover -s tests -t .` → `Ran 90 tests ... OK (skipped=5)` (was 87 at audit time; `tests/test_julesjordan.py` added since) |
| All 16 `known_bug` markers **already removed** | only the definition in `helpers.py:41` remains |
| **Frozen build now works** | `build.log` ends "Build complete!"; `backend\dist\Obscura\Obscura.exe` (8.9 MB) + `_internal\frontend` (31 files) + `_internal\scrapers` (24 `.py`) present |
| `PATCHES.md` cites tests that **do not exist** | `tests/test_security.py`, `tests/test_helpers.py`, `tests/dom_equivalence.js` all absent |
| Zero JS test infrastructure | no `package.json` anywhere in repo |
| **24 scraper files are gitignored** | `.gitignore:20` = `/scrapers/`; `git ls-files scrapers` → 0 files (count corrected from 25: one dir entry is `__pycache__`) |
| XSS via `${item.photo}` **already fixed** | `detail.js:429` now uses `esc(item.photo\|\|'')` |
| Host/Origin + per-run token middleware **present** | `server.py:41-61` `SecurityMiddleware` |
| 86 MB of debug build output is untracked and **not ignored** | `?? backend/build_dbg/` (28.8 MB), `?? backend/dist_dbg/` (57.2 MB) → new finding 11 |
| **Baseline (committed) suite fails 1 test in a fresh worktree** | `test_scanner.WalkTests.test_walk_...` — baseline `tests/helpers.py` lacks the `normpath` fix that exists only in the uncommitted corpus; disappears once P0 commits. Worktree run: 82 tests, 1 failure, 16 expected failures |

The Phase-0 ledger in `PHASE0.md` is **out of date**: every bug it tracks as open has
already been fixed in the working tree. The real risk has moved from "unfixed bugs" to
"a large body of unreviewed, uncommitted, partly-mis-documented work."


## Findings

| # | Finding | Severity | Plan |
|---|---|---|---|
| 0 | **Project goal:** must be a portable native-window app, never browser-based | High | [P0-DESKTOP](P0-DESKTOP-portable-native-app.md) |
| 1 | `scrapers/` is gitignored — ~230 KB of hand-written scrapers exist only on this disk | **Critical** | [P0](P0-repo-hygiene.md) |
| 2 | 1000+ lines of fixes uncommitted; no branch, no tag, `pyproject.toml` staged for deletion then re-added untracked | **Critical** | [P0](P0-repo-hygiene.md) |
| 3 | `PATCHES.md` / `PHASE0.md` describe tests and states that do not exist | High | [P0](P0-repo-hygiene.md) |
| 4 | ~~`Obscura.spec` points at `main.py` in the wrong directory — no build script~~ **RESOLVED in working tree** (spec moved to `backend/`, `build.bat` added, build completes); remaining: done criteria 2-4 unverified | High | [P0-DESKTOP](P0-DESKTOP-portable-native-app.md) |
| 5 | `run_yaml` fetches a scraper-supplied URL with **no SSRF guard** | High | [P1](P1-yaml-scraper-ssrf.md) |
| 6 | `_safe_image_url` is TOCTOU-vulnerable (resolve-then-fetch) | Medium | [P2](P2-ssrf-dns-rebinding.md) |
| 7 | App lock is **client-side only**; hash in `localStorage`, no backend check | Medium | [P3](P3-app-lock-is-client-side.md) |
| 8 | `restore` is `async def` doing blocking I/O — freezes the whole server | Medium | [P4](P4-restore-blocks-event-loop.md) |
| 9 | `/api/wipe` leaves `obscura.db.prev`, `posters/`, and free pages | Medium | [P5](P5-wipe-residue.md) |
| 10 | Frontend has zero automated tests despite being ~350 KB of JS | Medium | [P6](P6-frontend-test-harness.md) |
| 11 | 86 MB of `*_dbg` PyInstaller output untracked and unignored; 4 dead files ship in the release bundle | High | [P7](P7-build-artifacts-and-bundle-junk.md) |

## Recommended order

```
P7 (artifact/bundle hygiene) ─► DONE (branch executor-p7; user merge pending)
P0-DESKTOP ──────────────────► DONE (criteria 1-5 verified; user eyeball pending)
P0 (repo hygiene) ───────────► NEXT: merge executor-p7, then commit everything,
                               including the build fix

P1 (yaml SSRF)     ──┐
P2 (DNS rebinding) ──┼─► both touch server.py's fetch path; P2 depends on P1's helper landing first
P3 (app lock)      ──┘  independent, safe to parallelize
P4 (restore loop)  ──┐
P5 (wipe residue)  ──┴─► both backend/data lifecycle; independent of the above
P6 (JS harness)    ────► independent, but best done after P0 so the harness is itself committed
```

Two plans touch `db.py` and must not run concurrently: **P0-DESKTOP Step 3** (writable
`data/` fallback in `app_dir()`) and **P5** (wipe residue). Sequence them.

## Status

| Plan | Status |
|---|---|
| [P7](P7-build-artifacts-and-bundle-junk.md) — build artifacts & bundle junk | **DONE (branch `executor-p7`, commit `6140e3a`)** — reviewer-verified: bundle listing clean, findstr check empty, commit scope = `.gitignore` only. Pending user action: merge branch + delete the 4 untracked `frontend\` files in the main tree (they cannot cross the worktree boundary — untracked) |
| [P0-DESKTOP](P0-DESKTOP-portable-native-app.md) — portable native app | **DONE (verified 2026-10-05)** — criteria 1-5 all re-checked by the reviewer: clean build, runs from `%TEMP%\obscura-portable` (native window + WebView2 + HTTP 403 + 24 scrapers installed), fails legibly (modal box + `startup-error.log`), recreates `data\`, suite `Ran 90 OK (5 skipped)`. Remaining MANUAL eyeball: user opens `%TEMP%\obscura-portable\Obscura.exe`, confirms window renders + one live lookup; optional Step 5 (tkinter→native dialogs) declined as out of scope |
| [P0](P0-repo-hygiene.md) — repo hygiene | TODO |
| [P1](P1-yaml-scraper-ssrf.md) — yaml scraper SSRF | TODO (confirmed open: `scrapers.py:116` still fetches with no guard) |
| [P2](P2-ssrf-dns-rebinding.md) — DNS rebinding | TODO (after P1) (confirmed open: `_safe_image_url` resolve-then-fetch, no `net_guard`) |
| [P3](P3-app-lock-is-client-side.md) — app lock | TODO (confirmed open: lock screen in `ui.js:47`, no backend check) |
| [P4](P4-restore-blocks-event-loop.md) — restore event loop | TODO (confirmed open: `server.py:831` `async def` calls blocking `backup.restore_zip`) |
| [P5](P5-wipe-residue.md) — wipe residue | TODO (confirmed open: `server.py:798-820` no `POSTER_DIR`, no `.prev`, no `VACUUM`) |
| [P6](P6-frontend-test-harness.md) — frontend tests | TODO (no `package.json` yet) |

Status legend: TODO · PARTIAL (some steps verified done) · DONE · BLOCKED — executors may
update this column.
