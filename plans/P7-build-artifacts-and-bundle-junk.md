# P7 — Keep build artifacts and dev junk out of git and out of the release bundle

**Severity:** High (86 MB about to enter history; dead files shipping in the app) ·
**Effort:** Low · **Depends on:** nothing; run together with
[P0-repo-hygiene](P0-repo-hygiene.md), **before** its commit step.

## Boundary with P0

P0 decides *what gets committed*. This plan decides *what must never be committed* and
*what must never ship inside `dist\Obscura\`*. Three small edits, no application code.
Run it first in the same session — it makes P0's `git status` review trustworthy.

## Findings

### F1 — 86 MB of PyInstaller output is untracked but NOT ignored (High)

`.gitignore` contains `build/` and `dist/` (unanchored, so they match at any depth):
`backend\build\` and `backend\dist\` are ignored. The **debug variants are not**:

| path | contents | ignored? | in `git status` |
|---|---|---|---|
| `backend\build_dbg\` | 16 files, 28.8 MB | **no** | `?? backend/build_dbg/` |
| `backend\dist_dbg\` | 1174 files, 57.2 MB | **no** | `?? backend/dist_dbg/` |
| `backend\build\` | 16 files, 28.8 MB | yes | no |
| `backend\dist\` | 1174 files, 57.2 MB | yes | no |

Anything that stages broadly — an executor running `git add -A` / `git add .`, or a GUI
"stage all" — commits ~86 MB of binaries. That size is permanent: removing it afterwards
requires a history rewrite (`git filter-repo`), not a follow-up commit.

### F2 — The release bundle ships four dead developer files (Medium)

`backend/Obscura.spec` copies the whole frontend folder
(`datas=[('../frontend', 'frontend')]`), so everything sitting in `frontend\` lands in
`backend\dist\Obscura\_internal\frontend\` — verified on disk after the latest build:

```
patch.mjs          534 B    one-off script
_backup_css.txt  48572 B    byte-identical to _old_css.css (same SHA-256: 8B513F4B…)
_old_css.css    48572 B
_upgrade.css     9326 B
```

None of the four is referenced anywhere: searching `_old_css|_upgrade|_backup_css|patch.mjs`
across `frontend\index.html`, `frontend\js\*.js`, `frontend\fonts\fonts.css` returns **zero
hits**. They are also untracked in git, so today's release already contains files the
repository has never seen.

### F3 — Root/tooling files have no track-or-ignore decision (Low)

`git status --porcelain` `??` entries beyond app files:

- **Must be tracked** (other plans and the README reference them): `README.md`,
  `build.bat`, `backend/Obscura.spec`, `backend/pyproject.toml`,
  `tests/test_julesjordan.py`, `plans/`, `AGENTS.md`, `backend/session-abcd.diff`.
- **Must be ignored**: `.codegraph/` (its internal `.codegraph/.gitignore` ignores the DB
  and logs, but the directory still shows up because that file itself is untracked),
  `.agents/` (local skill installs), `build.log` (16 KB PyInstaller log, regenerated on
  every build).
- **Decide deliberately**: `skills-lock.json` (tooling lockfile — 494 B; commit it, it
  pins skill revisions).

`New Text Document.txt` is already listed in `.gitignore` — leave it alone.

## Steps

### Step 1 — extend `.gitignore`

Append to the existing `# python / build` block in `.gitignore` (do not touch the
`data/` / `*.db` rules above it):

```
# pyinstaller debug variants (build/ and dist/ already cover the default names)
build_dbg/
dist_dbg/
*.log

# local tooling state
.codegraph/
.agents/
```

Verify immediately:

```bat
git status --porcelain | findstr /i "dbg .codegraph .agents build.log"
```

Expected: **no output**. If `backend/dist/` or `backend/build/` still appear, the existing
rules are broken — stop and fix them before continuing.

### Step 2 — delete the four dead frontend files

```bat
del frontend\patch.mjs frontend\_backup_css.txt frontend\_old_css.css frontend\_upgrade.css
```

They are unreferenced (F2) and untracked, so this deletes nothing that git or the app
needs. If an old stylesheet is ever needed again it is in the history of
`frontend/index.html`, not in a loose `_old_css.css`.

### Step 3 — rebuild so the shipped bundle stops carrying them

```bat
build.bat
```

`_old_css.css` and friends must be gone from `_internal\frontend\`. The spec needs **no**
change for this — deleting the source files is the whole fix (an exclude list in `datas`
would be more code to maintain for the same result).

### Step 4 — prove the commit is clean

```bat
git status --porcelain
```

Every remaining `??` line must be a file from the "must be tracked" list in F3. Stage
those with explicit paths (per P0 — **never** `git add -A`), then re-run:

```bat
git diff --cached --name-only | findstr /i "data dist build dbg .db"
```

Expected: no `data\`, `dist\`, `build\`, `*_dbg*`, or `*.db` path in the staged list.

## Verification

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

Must still report `Ran 90 tests ... OK (skipped=5)` — this plan changes no Python source,
so any failure means the deletion in Step 2 hit something live; restore that file and
exclude it in the spec instead (escape hatch below).

```bat
build.bat
dir /b backend\dist\Obscura\_internal\frontend
```

Expected: `fonts`, `js`, `index.html`, `lucide.min.js`, `modern-screenshot.min.js` only.

## Files touched

- `.gitignore` — 4 new rules
- `frontend/patch.mjs`, `frontend/_backup_css.txt`, `frontend/_old_css.css`,
  `frontend/_upgrade.css` — deleted (all untracked today)
- No application source code changes; no spec change

## Maintenance note

`datas=[('../frontend', 'frontend')]` in `backend/Obscura.spec` means **anything** dropped
into `frontend\` ships in the next release. Keep scratch files outside that folder (a
root-level `scratch/`, itself gitignored). After any future build the cheap check is
`dir /b backend\dist\Obscura\_internal\frontend`.

## Escape hatch

If a file from F2 turns out to be live after all — for example a runtime fetch whose URL
is built dynamically so the grep could not see it — **STOP, do not delete it**. Move it to
`docs/` (outside `frontend\`, so it stops shipping), re-run Step 3, and report which file
was live and where it is referenced.

