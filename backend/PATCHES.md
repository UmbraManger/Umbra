# Obscura — Session A + B + C + D patches

Security (A), cryptography (B), robustness/hardening (C) and the app-lock
refactor (D) are recorded here as a reviewable patch history. The
session-abcd.diff referenced below was dropped from the repo in favor of
per-commit history — this document is the human-readable record.

Changed: backend/server.py, backend/main.py, backend/media.py, backend/crypto.py,
backend/db.py, backend/backup.py, backend/p1api.py, backend/algolia.py,
backend/scanner.py, backend/scrapers.py, frontend/index.html
(plus new frontend/js/, tests/, pyproject.toml, requirements.txt).
Unchanged: backend/keystore.py logic (annotation only).

---

## Session A — security

### A1. Per-run token + Host/Origin enforcement (server.py, main.py)
- Every /api/ call requires a per-run token (32 random bytes, regenerated at
  each launch), sent as X-Obscura-Token or ?t=.
- Host must be loopback (127.0.0.1 / localhost / ::1) -> blocks DNS rebinding.
- An Origin header must match the Host -> blocks cross-site fetch/form calls
  from other pages even with a valid token.
- CORS middleware removed entirely (the frontend is same-origin; * was the hole).
- Exception: plain GET /api/images/* and /api/media/* (img/video tags can't set
  headers) are allowed without a token only when Sec-Fetch-Site is
  same-origin/none/absent -> cross-site loads are rejected (403).

### A2. Image-id path traversal (server.py, crypto.py)
- img_id must match ^i[0-9a-f]{8}$ at the route AND inside
  crypto.load_image / remove_image. ..%2F...-style ids now return 404
  instead of escaping data/encrypted/.
- The record-delete image cleanup regex was tightened to the same shape.

### A4. Typed confirmation for destructive operations
- POST /api/wipe requires {'confirm':'DELETE MY LIBRARY'}.
- POST /api/backup/restore requires form field confirm=RESTORE.
- DELETE /api/{kind}/{rid}?file=1 requires confirm=DELETE, and refuses to
  delete a video file outside the configured scan folders (settings.dirs) -
  both checks run before any DB row is touched.
- Frontend modals send the new confirmations.

### A5. Command injection (media.py)
- reveal_in_os on Windows: explorer /select,... now runs as an argv list with
  shell=False; a crafted filename can no longer become shell syntax.

## Session B — cryptography (crypto.py)

- **No fast-hash oracle.** The stored SHA256(obscura::+pw) is gone. The
  passphrase is now verified by decrypting an AES-GCM *verifier* blob — a wrong
  passphrase costs a full KDF derivation, so imgprot.json is no longer an
  offline dictionary oracle.
- **Strong KDF.** Argon2id (t=3, m=64 MiB, p=4) via cryptography, with a
  PBKDF2-SHA256 @ 600k fallback; parameters are recorded in the meta file.
  (Legacy blobs keep PBKDF2-150k so they stay readable.)
- **Backward compatible.** Old v1 meta (hash + PBKDF2-150k) still opens:
  unlock()/set_passphrase() accept it and transparently rewrite the meta to
  the verifier format **keeping the same derived key** — no data re-encryption,
  no migration step needed.
- **No silent plaintext.** store_image raises Locked (HTTP 423) when
  protection is on but the vault is locked, instead of quietly writing
  plaintext. Blobs added while protection was off can be folded into the vault
  with the new POST /api/images/encrypt-all (needs unlocked).
- **Safe re-key.** set_passphrase is two-phase: everything is decrypted into
  memory first and a wrong passphrase or undecryptable file aborts the operation
  *before* anything is written (naming the offending file) — no more silently
  orphaned blobs. Rewrites are tmp + os.replace, with the originals kept in
  data/encrypted/.rekey-backup/ until the pass completes.

## Session C — robustness + leftover hardening

### P2 fixes
- **db.py**: positions table moved into SCHEMA (it was created ad-hoc in
  server.py, so any non-server consumer broke); scenes.gallery migration
  moved here too; migrations now catch sqlite3.OperationalError only instead of bare
  Exception.
- **media.py**: parse_range now also handles suffix ranges (bytes=-500) and
  raises RangeNotSatisfiable when the range is outside the file — server.py
  answers **416** with Content-Range: bytes /size instead of silently sending
  the whole file (which broke seeking in players).
- **p1api.py**: instance_token now read from the cookie jar (r.cookies.get)
  instead of hand-parsing set-cookie split on comma (which broke on HTTP dates).
- **algolia.py**: parse_date rewritten — ISO-8601 first, then explicit full
  formats, then date-prefix extraction; the old raw[:len(fmt)+5] heuristic
  mangled valid input and invented dates from junk. Returns None on garbage.
- **scanner.py**: guess_title handles the splitext('.mp4') dotfile quirk.
- **backup.py restore hardening**: the incoming DB is staged to
  obscura.db.incoming and validated (PRAGMA integrity_check + expected tables)
  **before** it replaces the live one; the previous library is kept as
  obscura.db.prev as a manual rollback point; the swap is atomic (os.replace).
- **server.py**: /api/scrape no longer logs the full request body (metadata
  only, at info level).

### Leftover hardening
- **Python-scraper opt-in gate** (the remaining RCE-by-design hole):
  - executing a Python scraper requires pyScrapers: true in settings (default
    **off**) — scrapers.run_python refuses otherwise;
  - uploading a .py requires confirm=understand python scrapers run as local code;
  - UI: a Python Scrapers: Allowed / Blocked toggle in Settings, and a required
    acknowledgement checkbox in the upload dialog. YAML scrapers are unaffected.
- **SSRF guard on _download_image / _safe_image_url** (net_guard.safe_get):
  only public http(s) endpoints — hostnames are resolved and loopback / private /
  link-local / reserved / multicast addresses rejected (covers 127.0.0.1,
  10.x, 169.254.169.254, ::1, file:...). Responses must be image/* and <= 15 MB
  before being stored.
- **XSS pass on index.html**: the remaining unescaped sinks — every
  scraper-fed image URL in src=... (cards, rows, cast chips, compare previews,
  lookup/AI results) now goes through esc() (which also closes attribute
  breakout via single quote in URLs). One lookup sink crashed on empty covers; fixed in
  the same edit. Text fields were already escaped.
## Session D — frontend module split (P3 refactor, frontend half)

- The 4,172-line monolithic script block is now 14 load-ordered classic
  modules (classic scripts keep the shared global scope, so this is
  semantics-preserving by construction — no import/export rewiring):
  utils.js · sync.js · state.js · views.js · lists.js · settings.js
  · ui.js · forms.js · lookup.js · player.js · detail.js · share.js
  · events.js · boot.js (15 modules including utils.js helpers).
- index.html: 336 KB / 4,765 lines → **47 KB / 609 lines** (head + CSS +
  markup + module tags). The per-run-token fetch wrapper stays inline in
  head so it wraps requests before any module runs.
- Each module re-declares use strict (the original block's directive no
  longer covers them).
- Verified behavior-identical two ways:
  1. textually: the stripped concatenation of js/*.js equals the original
     block byte-for-byte;
  2. node --check on every module.
- NOTE: a DOM-equivalence harness (tests/dom_equivalence.js, jsdom real page
  load) was planned but never materialized in this repo; the kept evidence is
  (1)+(2).
- The app lock is still client-side — the real server-side lock is planned
  (423 when locked): plans/P3-app-lock-is-client-side.md.

## Backend P3 (db schema versioning, type hints, logging, titlecase, lint, packaging)
- db.py schema versioning: PRAGMA user_version + ordered _MIGRATIONS
  (v1 = created_at/social columns, v2 = scenes.gallery) instead of ad-hoc
  try/except ALTERs; idempotent for pre-versioning databases, full type hints.
- Type hints completed across media.py, scanner.py, backup.py, crypto.py,
  keystore.py, db.py (parse_range, iter_file, load_image, import_file, ...).
- print → logging: image-download diagnostics go through
  logging.getLogger(obscura) instead of bare print.
- titlecase tool fixed: preserves ALLCAPS acronyms (BBC, XXX) and handles
  apostrophes and hyphens correctly.
- Lint: ruff clean under pyproject.toml config (correctness + unused
  names; the compact one-liner style E701/E702, grouped imports E401 and
  intentional lazy imports E402 are explicitly ignored, not churned). Real
  findings fixed: unused re import (scanner), unused clip_id (algolia),
  whitespace/EOF newlines.
- pyproject.toml + requirements.txt: pinned dep ranges, desktop extra
  for pywebview, dev extra for ruff; notes that cryptography>=42 is needed
  for Argon2id (older builds fall back to PBKDF2).

## Test evidence — 111 Python + 17 JS tests, all passing

The repo keeps ONE Python suite (stdlib unittest under tests/) plus the P6 JS harness:

- Run: & .venv/Scripts/python.exe -m unittest discover -s tests -t .
- Result: Ran 111 tests → OK, no skips (the 5 julesjordan tests unskipped once
  lxml was declared); the npm/jsdom harness runs 17 more (`npm test`) — see
  plans/P6-frontend-test-harness.md. One command for both: `tools\run_tests.bat`.
- Component files: tests/test_scrapers.py (22), tests/test_server.py (20),
  tests/test_crypto.py (19), tests/test_scanner.py (13), tests/test_media.py (12),
  tests/test_backup.py (11), tests/test_db.py (7), tests/test_julesjordan.py (5),
  tests/test_keystore.py (1).
  Every storage test runs in a throw-away temp folder via
  tests/helpers.IsolatedCase; the real data/ folder and the OS keyring are
  never opened.

## Known limits / next steps

- frontend/js/events.js (1,116 lines now) is still the fattest module — splitting
  the delegated click switch into per-domain handlers is the next tidy-up.