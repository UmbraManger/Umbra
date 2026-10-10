# P6 — The frontend has zero automated tests

**Severity:** Medium · **Effort:** Medium · **Depends on:** P0 (commit the harness itself)

**Status: DONE (2026-10-06).** Harness shipped: `package.json` + `package-lock.json`
committed, `node_modules/` gitignored, `tests/frontend/harness.js` + 4 test files
(`utils`, `state`, `security`, `boot`), and `tools/run_tests.bat` runs JS first then the
Python suite (preferring `.venv`). Numbers: **`npm test` → 19/19 pass; Python →
`Ran 124 tests … OK` (no skips — the 5 julesjordan tests unskipped once lxml
was declared)** — both from one command: `tools\run_tests.bat`.
Regression drill performed: broke `fmtDur` in `utils.js` → red at the exact assertion →
reverted → green. Three implementation deviations, all deliberate: (1) the npm script
globs `tests/frontend/*.test.js` instead of passing the directory — Node 22.22 treats a
directory arg as a literal test file and dies with `MODULE_NOT_FOUND`; (2) the harness
injects each file as a real `<script>` instead of `window.eval` — every module starts
`"use strict"`, so eval-scoped declarations never reach the shared global scope the
tests read back (script tags do, exactly like the browser); (3) `requestAnimationFrame`
is routed through the window's own timers — jsdom's `pretendToBeVisual` pump survives
`window.close()` and then crashes reading the torn-down location, failing otherwise-
green tests as uncaughtExceptions. No `frontend/js/*` source was modified (Option A).

## The finding

There is no `package.json` anywhere in the repository, no test runner, and no JS test
file. The frontend is roughly **350 KB across 15 modules** in `frontend/js/`:

| File | Size | File | Size |
|---|---|---|---|
| `detail.js` | 42 KB | `settings.js` | 37 KB |
| `events.js` | 63 KB | `lists.js` | 34 KB |
| `player.js` | 35 KB | `forms.js` | 26 KB |
| `ui.js` | 18 KB | `lookup.js` | 17 KB |
| `share.js` | 17 KB | `sync.js` | 12 KB |
| `views.js` | 12 KB | `state.js` | 10 KB |
| `utils.js` | 11 KB | `boot.js` | 3 KB |

The backend has 90 tests. The frontend has none.

This matters more than a raw coverage number would suggest, for three specific reasons:

1. **It was already designed once and thrown away.** `PATCHES.md` cites
   `tests/dom_equivalence.js` — a jsdom harness proving the `index.html` → `js/*.js`
   split was behaviour-identical, rendering byte-identical `#sidebar` and `#main` DOM.
   That file does not exist. The claim in `PATCHES.md` that the split was "verified
   behavior-identical three ways" is currently unverifiable.

2. **The riskiest frontend code is untested and partly hand-rolled.** `events.js`
   (1,116 lines) is one delegated click switch handling every action in the app
   (`data-action` dispatch — delete, wipe, restore, lock, re-key, scrape). A typo in a
   case label silently breaks a feature. `PATCHES.md` itself flags this file as the
   next tidy-up: *"js/events.js (1,049 lines) is still the fat one — splitting the
   delegated click switch into per-domain handlers is the next tidy-up."* Splitting it
   without tests is a gamble.

3. **Two of the audit's other findings live here.** P3 (the cosmetic app lock) is
   entirely `frontend/js/events.js` + `state.js`. It is untestable today, which is part
   of why it drifted.

Node v22.22.0 is available on this machine, so nothing blocks starting.

## Scope this deliberately
## Steps

### Step 1 — Set up a minimal harness

Create `package.json` at the repo root:

```json
{
  "name": "obscura-frontend",
  "private": true,
  "scripts": {
    "test": "node --test tests/frontend/"
  },
  "devDependencies": { "jsdom": "^25.0.0" }
}
```

Use Node's **built-in** test runner (`node:test` + `node:assert`) — available in Node 22
with no framework dependency. Add only `jsdom` for DOM-dependent tests.

```bat
cd /d "C:\Users\Devin Bolivar\Downloads\Video\Obscura"
npm install
```

Commit `package.json` and `package-lock.json`. **Do not commit `node_modules/`** — add
it to `.gitignore` (and note `.gitignore` already excludes `/scrapers/`, which P0
remediates; do not repeat that mistake here).

### Step 2 — Make the modules loadable in a test

`frontend/js/utils.js` is the highest-value target: pure helpers, no DOM dependency for
most of it — parsing utilities, `srt_to_vtt`, `mime_for`, date parsing, the
`sha256`/`deriveKey` helpers, and the corrupt-localStorage recovery logic at
`utils.js:88-97`.

The obstacle: these are classic script-tag globals (`function foo(){}` at top level,
no module exports), loaded via `<script src="js/utils.js">`. To test them, either:

- **Option A (recommended):** load the file into a jsdom window via
  `fs.readFileSync` + `window.eval`, then read `window.<fn>`. No source changes, and it
  tests the file exactly as the browser gets it.
- **Option B:** convert to ES modules with `export`. Cleaner long-term, but a large
  diff across every module and it changes how `index.html` loads them. **Out of scope
  for this plan.**

Go with A. Write one small shared helper in `tests/frontend/harness.js` that boots a
jsdom window, evaluates the needed `frontend/js/*.js` files in the correct order, and
returns the window — then every test file reuses it.

The load order matters; mirror `index.html:679-692`:

```
utils.js, sync.js, state.js, views.js, lists.js, settings.js, ui.js,
forms.js, lookup.js, player.js, detail.js, share.js, events.js, boot.js
```

Many modules reference globals defined in earlier ones, so a partial load will throw.

### Step 3 — Write the first tests, highest value first

Create `tests/frontend/`:

1. `utils.test.js` — the pure helpers. Include the **corrupt-localStorage** path
   (`utils.js:88-97`): seed `localStorage['obscura:encimgs']` with invalid JSON, call
   the reader, assert it returns `{}` and that a `corrupt-<timestamp>` key was written
   rather than throwing. This is defensive code nobody has ever executed.
2. `state.test.js` — settings merge/round-trip (`state.js:44-83`), including the
   settings-shape defaults at `:37` and `:55`. This is the module P3 touches.
3. `security.test.js` — assert that every `innerHTML` interpolation of untrusted data in
   `detail.js` passes through the `esc()` helper. A lightweight version: read the source
   of `detail.js`, regex for `` `<img src="${ `` and similar patterns **not** wrapped in
   `esc(`, and fail if any are found. This is a lint-style guard, not a runtime test,
   but it locks in the fix for the XSS class `PHASE0.md` flagged at `detail.js:422` and
   keeps it from regressing as more renderers are added.
4. `boot.test.js` — the `document.body.dataset.booted = '1'` contract (`boot.js:38`).
   The deleted `dom_equivalence.js` used exactly this as its readiness signal, which is
   a good precedent. Assert boot completes without throwing.

### Step 4 — Wire it into the same command as the Python suite

`tools/run_tests.bat` currently runs only unittest. Extend it so one command runs both,
and so a JS failure fails the batch:

```bat
call npm test
if errorlevel 1 exit /b 1
```

Order matters: run the JS tests **first** (fast, no venv needed), then Python. Note
that `tests/frontend/` must not be picked up by `python -m unittest discover -s tests`
— it only globs `test*.py`, so a `.test.js` naming convention keeps the two suites from
interfering.

### Step 5 — Verify

```bat
npm test
tools\run_tests.bat
```

Both suites pass. Then confirm the harness actually catches a regression: temporarily
break something small in `utils.js`, watch a test fail, revert. A test suite that has
never failed is not evidence of anything.

## Files touched

- `package.json`, `package-lock.json` — **new**
- `.gitignore` — add `node_modules/`
- `tools/run_tests.bat` — run both suites
- `tests/frontend/harness.js` — jsdom loader helper
- `tests/frontend/*.test.js` — 4 new test files
- `frontend/js/*` — **no changes** (Option A)

## Maintenance note

Every new `frontend/js/` module should get at least a smoke test asserting it loads in
the harness without throwing. That alone would have caught a missing `js/` file at
deploy time — `PATCHES.md` itself warns that *"a lone copied `index.html` will show the
existing 'App Did Not Finish Loading' toast instead of silently half-working."* A boot
smoke test converts that silent breakage into a red test.

## Escape hatch

If loading the full script chain in jsdom proves unreliable — the modules touch
`window` globals and `sync.js` starts timers/network on load — do **not** refactor the
frontend to make it testable as part of this plan. Narrow the harness to the modules
that load cleanly (`utils.js`, `state.js`) and note the others as future work. A partial
harness that runs is worth more than a complete one that never gets finished.

The goal is **a regression harness for the logic that is easy to break**, not 100%
coverage of a 350 KB codebase. Target the specific modules with pure, testable logic.