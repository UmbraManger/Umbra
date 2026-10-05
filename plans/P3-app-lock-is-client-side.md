# P3 — The "App Lock" is cosmetic: it protects nothing

**Severity:** Medium · **Effort:** Medium · **Depends on:** nothing

## The finding

Obscura advertises an app lock in its UI ("Password Saved - App Lock Enabled",
`frontend/js/events.js:673`). It does not lock the application. It is a client-side
overlay stored entirely in the browser.

How it works, end to end:

- `state.js:37` — `lock:{on:false,hash:''}` lives in the app's settings object
- `state.js:64` — the whole settings blob is read from `localStorage` key `obscura:v1`
- `state.js:83` — written back with `localStorage.setItem('obscura:v1', ...)`
- `events.js:663-673` — enabling it stores `settings.lock.hash = await sha256(np)`
- `boot.js:37` — on startup, `if(settings.lock.on) lockApp()`

Every one of those is attacker- or user-reachable with no secret involved:

1. **The hash is in `localStorage`.** Anyone who can open devtools — or any script on the
   page — reads `obscura:v1` and sees the hash directly.
2. **The comparison is in the client.** `passMatches(cur.value, settings.lock.hash)`
   (`events.js:665`) runs in the page. Setting `localStorage.obscura:v1` to
   `{"lock":{"on":false}}` skips the lock entirely; a reload shows the whole library.
3. **The data is not encrypted by it.** `settings.lock` does nothing to the SQLite
   library, the `data/encrypted/` blobs, or the images. Note the contrast: image
   protection *is* real, because `crypto.py` holds the key in the server process and
   refuses to decrypt when locked (`crypto.load_image` raises `Locked`).
4. **It does not lock the backend.** Nothing in `server.py` reads `settings.lock`. With
   the app "locked", `curl` against the local API still works exactly as before. There
   is no server-side lock state to consult.

So a user who enables this believes they have protected a private media library against
someone with physical access to the machine. They have not. This is the most
trust-relevant gap in the codebase, because it is a *false assurance* rather than a
missing feature.

## Decide first: fix, re-label, or remove

This is a product decision. Present these to the user rather than picking silently:

- **Option A — make it real.** Server-side lock state; the API refuses data reads while
  locked. This is what the UI already implies.
- **Option B — re-label it honestly.** Rename to "Privacy Screen" / "Hide Window On
  Start", keep it purely cosmetic, and state in the UI that it does not encrypt
  anything. Cheapest, and removes the false assurance.
- **Option C — remove it.** Delete the feature and its settings entries.

Recommend **A** if the user wants the feature, **B** if they want it this week. Do not
ship a third option that keeps the name and adds a tooltip — that keeps the misleading
label.

### If Option A (server-side lock) — the steps

1. **Add lock state to `crypto.py`.** A module-level `_locked: bool` plus
   `set_locked(bool)`, `is_locked()`. The vault is already the natural home: image
   protection already has exactly the "unlock before serving" semantics needed.

2. **Enforce it in `server.py`.** The cleanest enforcement point is
   `SecurityMiddleware.dispatch` (`server.py:41`) — reject data endpoints with
   `423 Locked` when locked. Exempt a small allowlist: `/api/ping`,
   `/api/images/unlock`, `/api/images/status`, and the frontend static mount (or the
   user cannot even load the unlock dialog).

3. **Add endpoints.** `POST /api/lock` and `POST /api/unlock`, mirroring the existing
   `POST /api/images/unlock` (`server.py:284`) shape — reuse its `PassBody` model and
   its verification path rather than inventing a second convention.

4. **Verify the hash.** Use a **slow** KDF for the lock password, not bare SHA-256 as
   `events.js:670` does today. `crypto.py` already has `_derive()` with Argon2id and a
   PBKDF2 fallback — reuse it, exactly as `crypto.set_passphrase` does. Store salt +
   params, never a bare hash.

5. **Move verification server-side.** The client sends the password; the server
   derives and compares. The client must not hold or compare the hash at all.

6. **Call it on boot.** `main.py` starts the server — have it read the lock flag from
   `db.get_settings()` and initialise the locked state before serving.

### If Option B (re-label) — the steps

Much smaller: update the strings in `events.js` (`:673` and the modal at `:593`) and
`state.js:37`, and add one line of UI text making the limitation explicit. No backend
change. Then also apply the honest naming to the settings panel.

## Tests

For Option A, add to `tests/test_server.py` (which already has the `SecurityMiddleware`
tests and the `TestClient` harness — follow
`test_wipe_and_restore_need_explicit_confirmation` as the pattern):

1. `test_locked_api_returns_423` — lock, then assert a data endpoint returns 423.
2. `test_unlock_with_wrong_password_fails` — assert 403 and still locked.
3. `test_unlock_with_correct_password_opens_api` — assert 200.
4. `test_unlock_endpoint_reachable_while_locked` — the lockout must not deadlock the app.
5. `test_lock_survives_restart` — lock, `db.close()`/`db.connect()`, assert still locked.

For Option B, no backend tests; verify by loading the UI.

## Files touched

Option A: `backend/crypto.py`, `backend/server.py`, `backend/main.py`,
`frontend/js/events.js`, `frontend/js/state.js`, `frontend/js/boot.js`,
`tests/test_server.py`.

Option B: `frontend/js/events.js`, `frontend/js/state.js` (and the settings panel).

## Maintenance note

Whatever ships, the UI copy must match the mechanism. The root cause of this finding is
that a security label was written before the mechanism existed. Any future security
toggle needs a backend counterpart in the same commit.

## Escape hatch

If the user picks Option A but the token/Origin middleware in `SecurityMiddleware`
proves hard to extend with the lock check (it already handles token, Host, Origin, and
`Sec-Fetch-Site`), do **not** bolt the lock check onto individual route functions —
that guarantees a missed endpoint. Keep it in the middleware. If middleware ordering
becomes a genuine problem, STOP and report it.
`PHASE0.md` listed "App lock never engaging on backend start" as a Phase 1 item. It was
never addressed, and the underlying design is the actual problem.