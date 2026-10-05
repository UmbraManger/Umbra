# P2 — SSRF hardening: close the resolve-then-fetch gap and follow no redirects blindly

**Severity:** Medium · **Effort:** Medium · **Depends on:** P1 (shares `net_guard.py`)

## The finding

`backend/server.py:495-518` (moving to `backend/net_guard.py` per P1):

```python
def _safe_image_url(url: str) -> bool:
    import socket, ipaddress
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except Exception:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False
    return True
```

This is a good guard and a genuine improvement over nothing. But it validates the URL at
**one instant in time**, and the actual HTTP fetch happens later, in a different library,
which performs its **own** DNS resolution. Two concrete gaps:

### Gap 1 — DNS rebinding / TOCTOU (the real one)

The sequence is: `safe_image_url` resolves `evil.example` → gets a public IP → passes.
Then `requests.get` resolves `evil.example` **again**. Between the two lookups the
attacker updates their DNS record to `127.0.0.1` (TTL 0, or simply timing it). The
second resolution — the one that actually connects — is never checked.
## Steps

### Step 1 — Confirm the shared module from P1 exists

This plan edits `backend/net_guard.safe_image_url`, introduced by P1. If P1 has not run,
do it first. Do not create a second, divergent guard here.

### Step 2 — Disable automatic redirects and validate each hop

In `net_guard.py`, add a helper that performs the fetch with redirects disabled and
re-validates each `Location`:

```python
MAX_REDIRECTS = 3

def safe_get(session, url, **kw):
    """GET that re-validates every redirect hop against safe_image_url."""
```

Behaviour:

- `allow_redirects=False` on every request
- if status is 301/302/303/307/308 **and** hops remain, read `Location`, resolve it
  relative to the current URL (`urljoin`), run it through `safe_image_url`, and if it
  fails raise `ValueError`; otherwise follow and decrement
- if a redirect arrives with hops exhausted, raise `ValueError`
- pass `**kw` (timeout, headers) through untouched so call sites keep their current options

Then convert the two call sites to use it:

- `_download_image` in `server.py:534` — it currently branches between
  `iafd_scraper.iafd_session.get(...)` (`:555`) and a cloudscraper call (`:560`). Wrap
  the requests/cloudscraper calls. The `iafd_session` path shares the same exposure;
  route it through `safe_get` too, or explicitly document why it is exempt.
- `run_yaml` in `scrapers.py:116` — currently `requests.get(target, ...)`.

Keep the `safe_image_url` check at the entry of both call sites too. Defence in depth:
the pre-check catches the obvious case cheaply, `safe_get` catches what happens after.

### Step 3 — Decide honestly whether to close the DNS-rebinding gap

Closing TOCTOU properly requires connecting to a **specific validated IP** rather than
re-resolving — i.e. a custom `requests` adapter that pins the resolved address, plus
manual `Host`/SNI handling for TLS. That is a substantial, bug-prone change to a
codebase whose HTTP paths mostly target Cloudflare-protected sites, where pinning an IP
frequently breaks certificate validation.

**Recommendation: do not implement IP pinning in this plan.** Instead:

1. Document the residual TOCTOU window in `net_guard.py`'s module docstring, stating
   plainly that the guard is a best-effort check against *configuration*, not a
   network-level sandbox.
2. Record the real mitigation, which already exists in the threat model: YAML scrapers
   are user-installed by definition, and Python scrapers require an explicit typed
   confirmation (`server.py:448`) plus a `pyScrapers` setting (`scrapers.py:83`). The
   primary defence is "only run scrapers you trust", not the URL filter.

Raise this with the user as a judgement call rather than silently skipping it. If they
want true network-level isolation, the correct answer is running scrapers in a
sandboxed subprocess — which `PATCHES.md` already lists under "Known limits / next
steps" as longer-term work.

### Step 4 — Tests

Extend the `net_guard` tests added in Step 4 of the P1 plan, in `tests/test_scrapers.py`:

1. `test_safe_get_blocks_redirect_to_loopback` — stub a session whose first response is
   `302` with `Location: http://127.0.0.1:8080/`; assert `ValueError`.
2. `test_safe_get_allows_public_redirect` — `302` to a public host; assert the second
   hop was requested.
3. `test_safe_get_stops_after_max_redirects` — a stub that always 302s to itself;
   assert `ValueError` after 3 hops.
4. `test_safe_get_rejects_https_to_http_downgrade` — decide policy deliberately; if
   downgrades are blocked, assert it.

All stubs — **no live network**. Follow the isolation pattern in `tests/helpers.py`.

### Step 5 — Verify

```bat
cd /d "C:\Users\Devin Bolivar\Downloads\Video\Obscura"
.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Then manually sanity-check that normal image downloads still work (the guard must not
break real CDN fetches) by running a scrape against one configured site.

## Files touched

- `backend/net_guard.py` — add `safe_get`, document residual TOCTOU risk
- `backend/server.py` — `_download_image` routes through `safe_get`
- `backend/scrapers.py` — `run_yaml` routes through `safe_get`
- `tests/test_scrapers.py` — redirect tests

## Maintenance note

Every future `requests`/`cloudscraper` call that takes a non-constant URL should use
`safe_get`, not bare `requests.get`. A grep for `requests.get` should return only
constant-URL call sites. Consider noting this in `PATCHES.md` once P0 has corrected it.

## Escape hatch

If redirect-aware fetching breaks legitimate scrapers — some sites redirect `http` to
`https` or through a CDN hop that resolves to a range you did not expect — **stop and
report the specific host and redirect chain.** Do not add a blanket allowlist or an
`allow_redirects=True` escape hatch to make it pass; that reintroduces Gap 2 exactly.

A local desktop app is a poor SSRF target for this in practice: the attacker needs to
control DNS for a hostname the user will fetch, which usually means they already
installed a malicious scraper. **Rate this honestly as defence-in-depth, not a live
exploit.**

### Gap 2 — Redirects are followed without re-validation

Both `_download_image` (`server.py:534`) and `run_yaml` use the default
`requests`/`cloudscraper` redirect behaviour, which follows `301`/`302` automatically.
`https://attacker.example/pic.jpg` → `302` → `http://127.0.0.1:8080/admin` is followed
happily. `safe_image_url` only ever sees the *original* URL. This is the more practical
of the two, because the attacker only needs an open redirect on a host they control —
no DNS control, no timing.