# P4 — `POST /api/backup/restore` blocks the event loop for the whole restore

**Severity:** Medium · **Effort:** Low · **Depends on:** nothing

## The finding

`backend/server.py:827-835`:

```python
@app.post("/api/backup/restore")
async def backup_restore(file: UploadFile = File(...), confirm: str = Form("")):
    if confirm != "RESTORE":
        raise HTTPException(400, 'confirmation required: send form field confirm="RESTORE"')
    data = await file.read()
    try: n = backup_engine.restore_zip(data)
    ...
```

`backup_restore` is declared `async def`, so FastAPI runs it **on the event loop**.
`restore_zip` (`backend/backup.py:88-173`) is entirely blocking synchronous work:

- reads and decompresses every member of the uploaded zip into a staging dir (`:99-113`)
- copies the DB out and runs `PRAGMA integrity_check` on it (`:121-133`) — a full
  database scan
- `shutil.copy2` of the entire live database to `obscura.db.prev` (`:145`)
- `os.replace` of every restored file (`:149-153`)
- `db.close()` then `db.connect()`, which re-runs the whole schema migration (`:139`, `:155`)

The user is restoring a library whose `data/encrypted/` directory here holds **thousands
of blobs** and whose `obscura.db` is ~1.2 MB with a ~366 KB WAL. That is seconds of
solid CPU and disk I/O.

Because this occupies the single event loop thread, **the entire server is frozen** for
that duration: no API calls, no media streaming, no UI progress. The browser's fetch
just hangs. The user cannot even cancel.

`PHASE0.md` explicitly listed "restore blocking the event loop" as an open Phase 3 item.
It was not done.

Note the contrast with the rest of the file: `image_upload` (`server.py:290`) and
`scraper_upload` (`:448`) are `async` but only do `await file.read()` before delegating.
`backup_export` (`:820`) is correctly `def`, so FastAPI runs it in a threadpool. Restore
## Steps

### Step 1 — Offload the blocking call

The minimal, correct fix is to run `restore_zip` in a worker thread. FastAPI's
`run_in_threadpool` is already available via `starlette.concurrency`:

```python
from starlette.concurrency import run_in_threadpool
...
    try: n = await run_in_threadpool(backup_engine.restore_zip, data)
```

This keeps the `async def` endpoint (so the `await file.read()` stays non-blocking) and
returns the loop to the event loop for the duration.

Do **not** "fix" this by changing the endpoint to plain `def`. That would work too —
Starlette auto-threadpools sync endpoints — but it would make `await file.read()`
illegal and force a signature change for no benefit. Use `run_in_threadpool`.

### Step 2 — Confirm `backup_export` is fine, and say so in a comment

`backup_export` (`server.py:820`) is already sync and therefore already threadpooled.
Confirm it is not slow enough to matter; `export_zip` does a full `db.backup()` plus
`VACUUM` (`backup.py:76`), and `VACUUM` on a 1.2 MB DB is milliseconds. Leave it — but
add a comment noting the threadpool behaviour is deliberate, so nobody "tidies" it into
an `async def` later and reintroduces P4's bug on the export side.

### Step 3 — Add a size guard on the upload

`await file.read()` loads the entire zip into memory with no cap. A multi-GB upload
would be read fully before `restore_zip` rejects it. Reject early on `Content-Length`:

- If `Content-Length` is present and exceeds a sane cap (the archive contains the whole
  library — 50 MB is generous), return `413` before reading.
- Keep the cap generous. Do not pick a value that would break a real large library; if
  unsure, check what the user's own export size actually is via
  `GET /api/backup/export` and set the cap well above it.

Streaming the body to a temp file instead of `await file.read()` would be strictly
better, but it is a larger change to the `restore_zip(data: bytes)` signature — only do
it if the size guard proves insufficient.

### Step 4 — Report progress, or at least fail gracefully

While the restore runs in a thread, the UI has nothing to show. Check
`frontend/js/settings.js` for the restore call. At minimum, ensure the button shows a
busy state and that a failure surfaces the server's error message rather than a generic
"request failed".

If you add progress reporting, note that it is not straightforward: the single POST
holds the connection. A pragmatic option is an indeterminate spinner plus a note that
the app will be unresponsive during restore. Do **not** build a job-queue/websocket
progress system as part of this plan — that is a feature, not a fix.

## Tests

Add to `tests/test_server.py`, following the existing restore-confirmation test
(`test_wipe_and_restore_need_explicit_confirmation`) for the harness pattern:

1. `test_restore_does_not_block_the_event_loop` — the important one. Start a restore of
   a non-trivial archive in a background thread, then issue a `GET /api/ping` from the
   test thread and assert it returns within a short timeout while the restore is still
   running. Without `run_in_threadpool` this test hangs or times out; with it, it passes.
   Guard the whole test with a timeout so a regression fails rather than hangs — the
   repo already has `faulthandler.dump_traceback_later(240, exit=True)` in
   `tests/helpers.py` as a backstop.
2. `test_restore_rejects_oversized_content_length` — send a request declaring a
   `Content-Length` over the cap; assert `413`.
3. Keep the existing confirmation test passing unchanged.

## Files touched

- `backend/server.py` — `run_in_threadpool` at `:832`, upload size cap, comment on
  `backup_export`
- `frontend/js/settings.js` — busy state on restore (only if not already present)
- `tests/test_server.py` — the two new tests

## Maintenance note

Any future endpoint that calls a blocking `backup_engine` / `db` / filesystem function
must either be declared plain `def` (auto-threadpooled) or explicitly wrap the blocking
call in `run_in_threadpool`. `restore_zip` and `export_zip` are the expensive ones.

## Escape hatch

If moving the work off the loop exposes a **thread-safety** problem — `db.py` uses a
module-level `_conn` with `check_same_thread=False` and an `RLock` (`db.py:39-57`), and
`restore_zip` calls `db.close()`/`db.connect()` — do **not** paper over it by re-adding
a global lock around the whole endpoint. That would reintroduce the freeze. Instead
report it: the correct resolution is for restore to take the DB out of service
explicitly (close, replace, reopen) with concurrent requests rejected, which is a
larger design change than this plan.
is the one endpoint that got the `async` treatment without the offload.