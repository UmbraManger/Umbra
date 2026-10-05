# P1 — SSRF: the YAML scraper path fetches attacker-chosen URLs unguarded

**Severity:** High · **Effort:** Low · **Depends on:** nothing (do before P2)

## The finding

`backend/scrapers.py:108-116`, function `run_yaml`:

```python
def run_yaml(path: str, title: str = "", url: str = "") -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    target = url
    if not target:
        tpl = (cfg.get("search") or {}).get("url", "")
        if tpl and title: target = tpl.replace("{title}", quote(title))
    if not target: raise ValueError("no url and no search template in yaml")
    r = requests.get(target, timeout=25, headers={"User-Agent": "Mozilla/5.0 (Obscura)"})
```

`target` comes from two fully attacker-controllable places — the caller-supplied `url`
argument and the `search.url` template inside the uploaded YAML file — and it goes
straight into `requests.get` with **no validation whatsoever**.

Meanwhile `backend/server.py:495` already contains a purpose-built SSRF guard,
`_safe_image_url`, which rejects non-http(s) schemes and any host resolving to
loopback/private/link-local/reserved/multicast addresses. `_download_image`
(`server.py:538`) calls it before every fetch. **`run_yaml` does not.**

`PHASE0.md` flagged this exact gap in its "Not covered by tests yet" section as
Phase 2 work. It was not done.

## Why it matters here

Obscura binds a local HTTP server on loopback. An attacker who can get a YAML scraper
installed — or who can get a user to run one with a chosen `url` — can make the host
issue GET requests to `http://127.0.0.1:<port>/...`, `http://169.254.169.254/latest/meta-data/`
(cloud instance metadata), or any RFC1918 address on the user's LAN.

The realistic impact is bounded but real: this is a **GET-only** primitive (no request
body, no header control beyond User-Agent), and the response is fed to BeautifulSoup
rather than returned raw, so it is a *blind* SSRF — the attacker learns little directly.
The practical risks are (a) port-scanning the user's LAN by timing/error differences,
(b) triggering state-changing `GET` endpoints on internal services (many devices have
them), and (c) reaching cloud metadata endpoints on a laptop running in a cloud VM.
## Steps

### Step 1 — Move the guard somewhere both callers can reach it

`_safe_image_url` currently lives in `server.py`, but `scrapers.py` is imported by
`server.py` — importing *from* `server` into `scrapers` would create a circular import
(`server` imports `scrapers` at module load).

Promote the function to a neutral module. Create `backend/net_guard.py` containing
`_safe_image_url` renamed to `safe_image_url`, moved verbatim plus its `socket` /
`ipaddress` imports hoisted to module top. Keep the docstring and behaviour identical.

Then:

- `server.py`: replace the local definition with
  `from net_guard import safe_image_url` and update the single call site
  (`server.py:538`, `_safe_image_url(url)` → `safe_image_url(url)`).
- Verify no other `_safe_image_url` references remain:
  `Select-String -Path backend\*.py -Pattern '_safe_image_url'`

Note: `backend/` modules are imported as top-level names (`tests/helpers.py` puts
`backend/` on `sys.path` and does `import db`, `import crypto`), so `from net_guard
import safe_image_url` — not a relative import — is the correct form. Match that.

### Step 2 — Guard both `target` sources in `run_yaml`

After `target` is resolved and before `requests.get`, add:

```python
if not net_guard.safe_image_url(target):
    raise ValueError("blocked unsafe scraper target URL (private/loopback address)")
```

Place it **after** the `if not target:` check and **before** the `requests.get` call.

Guarding here (rather than inside `safe_image_url` itself) covers both injection
points — the caller-supplied `url` and the YAML `search.url` template — with one check.

### Step 3 — Guard every other fetch site in the module

Read `run_by_id` (`scrapers.py:132`) and `run_for_site` (`scrapers.py:164`). If either
can reach a network fetch with a scraper-supplied URL, apply the same one-line guard.
Find them all:

```bat
Select-String -Path backend\scrapers.py -Pattern 'requests\.(get|post)|urlopen|session\.get'
```

Guard each site that takes a non-constant URL.

### Step 4 — Add regression tests

Add to `tests/test_scrapers.py`, which already imports the module and follows the
`IsolatedCase` pattern from `tests/helpers.py`:

1. `test_run_yaml_blocks_loopback_target` — a temp YAML file whose `search.url` is
   `http://127.0.0.1:9/x`; assert `ValueError` is raised and that **no** socket
   connection was attempted.
2. `test_run_yaml_blocks_cloud_metadata_target` — template pointing at
   `http://169.254.169.254/latest/meta-data/`; assert `ValueError`.
3. `test_run_yaml_allows_public_https` — with the guard satisfied, assert the function
   proceeds to the fetch (stub `requests.get` so no real network call happens).
4. `test_run_yaml_rejects_non_http_scheme` — `file:///C:/Windows/win.ini`.

**Do not make these live network calls.** Patch `scrapers.requests.get` with a stub
that records the call and returns a minimal fake response. Follow the isolation
conventions in `tests/helpers.py` — these tests touch no real `data/` folder.

Add matching unit tests for the guard itself, in the style of the existing
`test_scrapers.py` cases: `safe_image_url("http://127.0.0.1/")` is `False`,
`safe_image_url("http://169.254.169.254/")` is `False`,
`safe_image_url("http://10.0.0.1/")` is `False`, `safe_image_url("not-a-url")` is `False`.

### Step 5 — Verify

```bat
cd /d "C:\Users\Devin Bolivar\Downloads\Video\Obscura"
.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Done means the suite still reports `OK`, the new tests are present and passing, and
a manual `run_yaml` against a loopback URL raises `ValueError` rather than hanging on
a connection.

## Files touched

- `backend/net_guard.py` — **new**; hosts `safe_image_url`
- `backend/server.py` — drop the local `_safe_image_url`, import from `net_guard`,
  update the `:538` call site
- `backend/scrapers.py` — add the guard in `run_yaml` (and any other fetch site found)
- `tests/test_scrapers.py` — new regression tests

## Maintenance note

Any new outbound HTTP call added to this codebase must go through `net_guard`.
`PHASE0.md` already anticipated a fuller `net_guard` module (it also envisioned
covering `_safe_image_url` redirect and DNS-rebinding bypasses) — **P2 extends this
same module**, so keep the two changes in the same file and review them together.

## Escape hatch

If guarding `run_yaml` turns out to break legitimate scrapers that intentionally target
a LAN-hosted or self-hosted service, do **not** weaken the guard to a warning. Instead
add an explicit, per-scraper opt-in stored in the scraper's `meta.json` and clearly
surfaced in the UI — a deliberate user decision, not a silent default. If no such
opt-in is warranted, STOP and report back rather than adding a bypass flag.

It is trivially fixable and the fix already exists in the codebase.