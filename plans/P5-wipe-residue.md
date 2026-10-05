# P5 — `/api/wipe` leaves the old library recoverable on disk

**Severity:** Medium · **Effort:** Low · **Depends on:** nothing

## The finding

`backend/server.py:795-817`:

```python
@app.post("/api/wipe")
def wipe_all(body: dict = Body(default={})):
    if (body or {}).get("confirm") != "DELETE MY LIBRARY":
        raise HTTPException(400, '...')
    for table in TABLES: db.execute(f"DELETE FROM {table}")
    db.execute("DELETE FROM positions")
    db.execute("DELETE FROM settings")
    for d in (enc_dir, scraper_dir): shutil.rmtree(...); os.makedirs(...)
    for f in ("scanstate.json", "imgprot.json"): os.remove(...)
    return {"ok": True}
```

The rows are deleted, and the endpoint reports success. But a user who clicks
"DELETE MY LIBRARY" — on a shared or borrowed machine, before selling a laptop, or
simply meaning it — is not getting what the confirmation promised. Three residues:

### R1 — `obscura.db.prev` still holds the entire library

`backup.restore_zip` writes a full copy of the pre-restore database to
`db.DB_PATH + ".prev"` (`backup.py:143-145`). `wipe_all` never removes it. So after a
wipe, a complete copy of every movie, scene, performer, studio, and category — titles,
descriptions, file paths, performer names — sits in `data/obscura.db.prev`, byte for
byte. It is not in any table, so nothing in the UI will ever show it. But it is the
single most sensitive artefact in the data directory, and it is trivially recoverable
by anyone who copies the folder.

### R2 — The SQLite file itself still contains the deleted rows

`db.execute` runs `DELETE FROM <table>` and commits, but SQLite does not zero freed
pages — it marks them reusable. The titles and descriptions remain readable in the raw
file, and in the `-wal` file, until a `VACUUM` reclaims them. Compare
`backup.py:61-76`, which already does exactly this dance for the AI key:

```python
con.execute("UPDATE settings SET value=? WHERE key='app'", (json.dumps(s),))
con.execute("VACUUM")   # so the old value is physically gone, not just unlinked
```

The comment there says it outright: *"an UPDATE alone would leave the old value in freed
## Steps

### Step 1 — Determine whether `posters/` is live or vestigial

```bat
cd /d "C:\Users\Devin Bolivar\Downloads\Video\Obscura"
Select-String -Path backend\*.py -Pattern 'POSTER_DIR|poster'
```

If nothing writes poster files, remove `POSTER_DIR` from `db.py` and its entry in
`ensure_dirs()`. If something does write them, add the directory to the wipe cleanup
alongside `encrypted/` and the scraper dir. Do not guess — an over-broad `rmtree` on a
directory the app uses would be a data-loss bug in the fix for a data-loss bug.

### Step 2 — Reclaim the SQLite pages

After the `DELETE` statements, run a `VACUUM` on the live connection so freed pages are
actually rewritten. `db.py` has no `vacuum()` helper — add one alongside `execute()`
that runs `VACUUM`, following the existing style:

```python
def vacuum() -> None:
    with _lock:
        connect().execute("VACUUM")
```

Then call `db.vacuum()` in `wipe_all` after the deletes.

Note `VACUUM` needs a temp file and cannot run inside a transaction — if it raises
`OperationalError` here, that is why; make sure it is called after the deletes have
committed. Also consider `PRAGMA wal_checkpoint(TRUNCATE)` so the `-wal` file does not
retain the deleted content.

### Step 3 — Remove the `.prev` rollback copy

After the vacuum, remove `db.DB_PATH + ".prev"` (and any `-wal`/`-shm` siblings of it).
The rollback point is a restore-time convenience; after an explicit, confirmed wipe it
is the whole problem.

Order matters: vacuum first, then delete `.prev`.

### Step 4 — Extend the test

`tests/test_server.py` already has `test_wipe_empties_the_library`. Extend it (or add
`test_wipe_leaves_no_recoverable_data`) to assert, after a wipe:

1. `os.path.exists(db.DB_PATH + ".prev")` is `False`
2. the raw bytes of `obscura.db` do **not** contain a distinctive title string that
   existed before the wipe — this is the assertion that catches R2, and it is the one
   that actually matters
3. the `-wal` file does not contain it either
4. the poster directory question from Step 1 is resolved and asserted accordingly

For (2) and (3), use a sentinel value like `"ZZTESTONLY-SENTINEL-TITLE"` as a record
title before wiping, then read the raw file as bytes and assert it is absent. Follow the
isolation conventions in `tests/helpers.py` — all of this happens in the per-test temp
folder, never the real `data/`.

Also read the `-wal` file, not just the main DB: SQLite may not have checkpointed the
deletes, so the sentinel can survive in the WAL even after a successful `VACUUM`.

## Files touched

- `backend/db.py` — add `vacuum()` (and possibly remove `POSTER_DIR`)
- `backend/server.py` — call it in `wipe_all`; delete `.prev`
- `tests/test_server.py` — the raw-bytes regression test

## Maintenance note

The general rule this plan encodes: **"deleted" and "gone" are different claims, and a
confirmed-destruction endpoint has to honour the second one.** Any future endpoint that
promises deletion — wipe, per-record delete with `file=1` — should be reviewed against
the same standard. `DELETE /api/{kind}/{rid}?file=1&confirm=DELETE` does correctly
scope its file deletion to `media.inside_roots` (`server.py:196-203`), so the residual
risk there is limited to the DB row, which the same VACUUM argument would apply to if
that is ever a concern.

## Escape hatch

If `VACUUM` on a large library turns out to be unacceptably slow (it rewrites the whole
file) and freezes the UI on the wipe endpoint, do **not** drop the vacuum — that
reintroduces R2, the actual finding. Instead run the vacuum through `run_in_threadpool`
as in P4 and let the endpoint wait for it, or show a confirmation that the step takes a
moment. If it is still too slow, report back: a wipe that cannot reclaim a multi-GB
database synchronously needs a different UX, not a weaker guarantee.
pages, still readable in the raw bytes."* `wipe_all` needs the same treatment, for far
more sensitive data.

Also note `data/obscura.db-wal` is ~366 KB on disk right now — a large share of the
deleted content is likely sitting there.

### R3 — `data/posters/` is never cleared

`db.POSTER_DIR` (`db.py:29`) is created by `ensure_dirs()` (`db.py:34-36`) and listed
as the poster directory, but `wipe_all` only removes `encrypted/` and the scraper dir.
Anything in `posters/` survives a wipe.

Caveat to check before acting: a grep of `backend/*.py` shows `POSTER_DIR` referenced
**only** in `db.py` (lines 29 and 35) — nothing writes to it. It may be dead code from
an earlier design. If so, the fix is to delete the constant and the `makedirs` call, not
to add cleanup for a directory nothing populates. Determine which before writing code.

`PHASE0.md` listed "wipe leaving `obscura.db.prev`, free pages and `posters/`" as an
open Phase 3 item. It was not done.