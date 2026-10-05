# P0 — Repo hygiene: protect untracked scrapers, commit the fix corpus, fix the docs

**Severity:** Critical · **Effort:** Low (mostly git) · **Depends on:** nothing

## Why this is first

This repository is one `rm -rf` or one bad clone away from losing work, and its own
documentation actively misleads the next person (or model) who reads it. Every other
plan in this directory is worthless if the code it modifies is not safely committed
first. Do this plan before touching anything else.

## Findings this plan fixes

### F1 — The entire scraper library is gitignored (CRITICAL, data loss)

`.gitignore:20` contains `/scrapers/`, and `git ls-files scrapers` returns **0 files**.
But `scrapers/` on disk contains 24 hand-written Python modules (25 entries — one is
`__pycache__`) totalling roughly
230 KB — `julesjordan.py` (25 KB), `xempire_scraper.py` (20 KB), `bangbros_scraper.py`
(19 KB), `sweet_pornstars.py` (15 KB), and 20 more.

This is a lot of hand-written domain logic. It is **not** in git, it is **not** in any
backup (`.gitignore` also excludes `backups/`, and the `backups/` snapshots only
capture `data/`, not `scrapers/`), and it exists on exactly one disk.

The `/scrapers/` ignore rule is almost certainly a copy-paste from the `data/` rule
above it — the author intended to protect *user data*, not the scraper source code.
Note `tests/test_julesjordan.py` imports `scrapers/julesjordan.py`, so the test suite
depends on a directory that git does not track: **a fresh clone cannot run the tests.**

### F2 — The whole fix corpus is uncommitted (CRITICAL)

`git log --oneline` shows exactly one commit, `147f909 "Baseline before fixes"`.
Everything since is uncommitted:

- Unstaged working-tree changes: 30 files, +1036 / −691
- Staged-but-uncommitted changes: 14 files, +520 / −1596

The staged set includes **deletions** of `backend/pyproject.toml` (30 lines) and
`backend/session-abcd.diff` (1391 lines). Both files nevertheless still exist on disk
as *untracked*. So the index says "delete", the disk says "keep", and a careless
`git checkout .` or `git stash` would destroy them.

There is no branch, no tag, and no second checkpoint since the baseline.

### F3 — The docs describe a repository that does not exist (High)

`backend/PATCHES.md` claims as test evidence:

- `tests/test_security.py` (11 tests) — **does not exist**
- `tests/test_helpers.py` (20 tests) — **does not exist**
- `tests/dom_equivalence.js` — **does not exist**
- "41 checks + DOM equivalence, all passing" — the real suite is **90 tests, 5 skipped**
### Step 2 — Un-ignore the scraper source, keep ignoring scraper *state*

Edit `.gitignore`. The `/scrapers/` line must go. But do **not** simply delete the rule
and commit everything — `scrapers/` may also hold user-installed scrapers and
`__pycache__`. Replace:

```
# scrapers/
/scrapers/
```

with:

```
# user-installed scraper state (meta.json) — but NOT the scraper source code,
# which is hand-written project code and must be versioned
__pycache__/
/scrapers/__pycache__/
/scrapers/meta.json
```

Verify what you are about to add before adding it:

```bat
git add -n scrapers/
```

Expect 24 `.py` files (a 25th entry is `__pycache__` — it must NOT be added). If `meta.json` or any `__pycache__` appears, fix the
ignore rules and re-check.

### Step 3 — Restore the two staged-deleted files into the index

They exist on disk as untracked; they only need to be tracked:

```bat
git add backend/pyproject.toml backend/session-abcd.diff
```

Confirm they are no longer staged as deletions:

```bat
git status --porcelain backend/pyproject.toml backend/session-abcd.diff
```

Both should now show as added/modified, **not** `D `.

### Step 4 — Decide what `session-abcd.diff` actually is, then commit it or delete it

`backend/session-abcd.diff` is a 1391-line patch document, and `PATCHES.md` refers to
it as the record of what changed. Read its first 40 lines. If it is purely a
human-readable summary of changes that are already in the code, it is redundant and
will go stale — delete it and let `PATCHES.md` (corrected in Step 6) be the record.
Keep it only if it contains information not otherwise recoverable.

### Step 5 — Commit the corpus as a series of reviewable commits

The repo's own rule (`PHASE0.md`) is **"one fix = one commit."** The current diff spans
security, crypto, media, DB migrations, and frontend work. Do not commit it as one
1,500-line lump — that defeats the point of having a baseline.

Suggested split, largest and most self-contained first:

1. `security: per-run token, Host/Origin enforcement, confirm gates` — `server.py`, `media.py`, `scrapers.py`
### Step 6 — Rewrite `PATCHES.md` and `PHASE0.md` to match reality

Both documents are stale and will actively mislead the next executor.

**`backend/PATCHES.md`** — the "Test evidence" section must be replaced with the real
numbers. Regenerate them:

```bat
cd /d "C:\Users\Devin Bolivar\Downloads\Video\Obscura"
.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Record the actual `Ran N tests` / `OK (skipped=M)` line. Delete the claims about
`test_security.py`, `test_helpers.py`, and `dom_equivalence.js` — or, if those tests
were genuinely written and then lost, say so explicitly. Do not leave a reader
hunting for files that are not there.

Also correct: `events.js` is described as "1,049 lines"; it is **1,116**.

**`PHASE0.md`** — the bug ledger's 16 rows are all fixed. Replace the table with a short
"Phase 0 complete" statement listing the 90-test suite as the safety net, and keep only
the genuinely-open items, which are now tracked in `plans/README.md`.

### Step 7 — Add the missing `requirements.lock.txt`

`requirements.txt` says: *"Unpinned on purpose: after your first successful run, execute
`pip freeze > requirements.lock.txt` and commit that file."* It was never done.

```bat
.venv\Scripts\python.exe -m pip freeze > requirements.lock.txt
```

Commit it. Unpinned dependencies plus a hand-maintained `pyproject.toml` is how a
working install silently breaks on a future `pip install`.

### Step 8 — Verify

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
git status --porcelain
git log --oneline
```

Done means:

- Suite still reports `OK` with the same test count as before the reorganisation
- `git status --porcelain` shows a clean tree except `plans/` and genuinely-intended files
- `git ls-files scrapers | Measure-Object -Line` returns 24, not 0
- `git ls-files backend/pyproject.toml` returns a line
- `git log --oneline` shows the 8 commits on top of `147f909`

### Step 9 — Confirm a clean clone actually works

The real test of this plan. Clone to a scratch directory and run the suite there:

```bat
git clone "C:\Users\Devin Bolivar\Downloads\Video\Obscura" %TEMP%\obscura-clone-check
cd %TEMP%\obscura-clone-check
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m unittest discover -s tests -t .
```

If `test_julesjordan.py` still skips or errors, the scraper library is still not fully
tracked. Fix that before declaring P0 done.

## Files touched

- `.gitignore` — replace `/scrapers/` rule
- `backend/pyproject.toml`, `backend/session-abcd.diff` — unstage the deletions
- `backend/PATCHES.md`, `PHASE0.md` — correct to match reality
- `requirements.lock.txt` — new
- `scrapers/*.py` — newly tracked (24 files)
- No application source code changes

## Maintenance note

Any future change touching `scrapers/` must remember these files are now versioned:
they get code review, and a bad edit is revertible. If the user later wants to drop
custom scrapers into the same folder, point them at a separate directory (e.g.
`data/scrapers/`, already gitignored via `data/`) rather than re-ignoring `scrapers/`.

## Escape hatch

If `git add -n scrapers/` reveals files that are **user data rather than project code**
— downloaded archives, a `meta.json` with personal site credentials, generated output —
STOP. Narrow the ignore rule to those specific paths and commit only genuine source.
Do not blanket-commit the folder to save time, and do not re-add `/scrapers/`.

---

## Runbook (quick reference — the user runs this in the project folder)

> **Shell warning:** the code block below uses `::` / `&::` comments, which only work in
> **cmd.exe**. In PowerShell they print errors. Run it in `cmd` (`Win+R` → `cmd` → `cd`
> into the project folder), or use the comment-free, shell-agnostic command blocks the
> advisor supplies in-session.

A faithful condensation of the Steps above; the steps remain the authority if anything
looks ambiguous. Run top to bottom from
`C:\Users\Devin Bolivar\Downloads\Video\Obscura`. **This plan must run in the main tree
(the fix corpus is uncommitted, so no git worktree can see it) and the advisor agent is
forbidden from committing to this branch — that is why this runbook is for you.**

```bat
:: 0. P7 leftovers first (branch merge + the 4 deletions, which cannot travel via git)
git merge executor-p7
del frontend\patch.mjs frontend\_backup_css.txt frontend\_old_css.css frontend\_upgrade.css

:: 1. snapshot (Step 1) — backups\ is gitignored
robocopy scrapers "backups\pre-p0\scrapers" /MIR
robocopy backend   "backups\pre-p0\backend"   /E /XD data

:: 2. .gitignore (Step 2): delete the "/scrapers/" line; add instead:
::      /scrapers/__pycache__/
::      /scrapers/meta.json
git add -n scrapers/            &:: expect exactly 24 .py files, nothing else

:: 3. undo the two staged deletions (Step 3)
git add backend/pyproject.toml backend/session-abcd.diff
git status --porcelain backend/pyproject.toml backend/session-abcd.diff   &:: no "D " left

:: 4. read the first 40 lines of backend/session-abcd.diff, then keep or delete it (Step 4)

:: 5. themed commits (Step 5) — stage EXPLICIT paths, NEVER git add -A:
::    1 security:   backend/server.py backend/media.py backend/scrapers.py + their tests
::    2 crypto:     backend/crypto.py tests/test_crypto.py
::    3 db:         backend/db.py tests/test_db.py
::    4 backup:     backend/backup.py tests/test_backup.py
::    5 scanner:    backend/scanner.py backend/media.py tests/test_scanner.py test_media.py
::    6 frontend:   frontend/index.html frontend/js/*
::    7 build:      backend/pyproject.toml backend/Obscura.spec build.bat README.md requirements*.txt
::    8 chore:      scrapers/ .gitignore tests/test_julesjordan.py plans/ AGENTS.md backend/PATCHES.md PHASE0.md
::    Before each commit: git status --porcelain -- the staged set must contain no
::    data\, backups\, *.db, dist\, build\ path.

:: 6. docs to reality (Step 6) — backend/PATCHES.md and PHASE0.md:
::    real numbers = "Ran 90 tests ... OK (skipped=5)"; delete the claims about
::    tests/test_security.py, tests/test_helpers.py, tests/dom_equivalence.js;
::    events.js is 1,116 lines (not 1,049); PHASE0's 16-bug ledger is fixed — keep only
::    genuinely-open items, now tracked in plans/README.md.

:: 7. lock file (Step 7)
.venv\Scripts\python.exe -m pip freeze > requirements.lock.txt
git add requirements.lock.txt && git commit -m "build: pin dependencies with requirements.lock.txt"

:: 8. verify (Step 8)
.venv\Scripts\python.exe -m unittest discover -s tests -t .     &:: must stay 90/OK/5 skipped
git ls-files scrapers | find /c ".py"                           &:: 24
git log --oneline                                               &:: the themed commits on 147f909

:: 9. clean-clone check (Step 9): clone into %TEMP%, python -venv, pip install -r
::    requirements-dev.txt, run the suite there — test_julesjordan must NOT skip.
```

Done = Steps 8 and 9 green. Only then can P1 and P2 be dispatched: their edits touch
`server.py` / `scrapers.py` / `test_scrapers.py`, which an isolated executor can only
see once the corpus is committed.

2. `crypto: Argon2id KDF, AEAD verifier, two-phase re-key` — `crypto.py`, `tests/test_crypto.py`
3. `db: versioned schema migrations via PRAGMA user_version` — `db.py`, `tests/test_db.py`
4. `backup: staged restore, AI-key scrub, code-execution gate` — `backup.py`, `tests/test_backup.py`
5. `scanner/media: cover ordering, titlecase, subtitle matching` — `scanner.py`, `media.py`, `tests/`
6. `frontend: split index.html into js/ modules` — `index.html`, `frontend/js/*`
7. `build: add pyproject.toml, pin dependency ranges` — `pyproject.toml`, `requirements*.txt`
8. `chore: version the scraper library, drop the /scrapers/ ignore` — `scrapers/`, `.gitignore`

Stage per-file and verify each with `git status --porcelain` before committing. Use
`git add -p` where a file mixes concerns.

**Never run `git add -A` for this step.** `backend/data/`, `backups/`, and `*.db` are
gitignored and must stay that way; confirm with `git status --porcelain` that no
`data/`, `backups/`, or `.db` path is staged.
- "`ruff` clean under `pyproject.toml` config" — `ruff` is not installed and
  `backend/pyproject.toml` is untracked

`PHASE0.md` claims 16 `known_bug` expected-failure tests and instructs the reader to
"delete that decorator in the same commit" as each fix. In reality **all 16 markers
are already gone** — the ledger describes a state the repo has already moved past.

A future executor reading `PATCHES.md` would reasonably conclude the security work is
untested and re-do it. That is expensive and risks regressing working fixes.

## Steps

### Step 1 — Snapshot before touching the index

Do this first, before any `git add`/`git checkout`:

```bat
cd /d "C:\Users\Devin Bolivar\Downloads\Video\Obscura"
mkdir "C:\Users\Devin Bolivar\Downloads\Video\Obscura\backups\pre-p0"
robocopy scrapers "backups\pre-p0\scrapers" /MIR
robocopy backend "backups\pre-p0\backend" /E /XD data
copy /Y backend\pyproject.toml backups\pre-p0\
copy /Y backend\session-abcd.diff backups\pre-p0\
```

`backups/` is gitignored, so this snapshot never enters the repo.