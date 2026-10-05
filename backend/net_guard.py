"""Shared SSRF guard for outbound fetches (server image downloads, scrapers).

Residual risk, deliberate (P2): safe_image_url resolves the host at *check*
time, but the real connection resolves it again later — a DNS-rebinding attacker
can answer the check with a public IP and the fetch with 127.0.0.1 (TOCTOU).
This guard is a best-effort check against *configuration*, not a network-level
sandbox; closing the window would need IP-pinning HTTP adapters with manual
Host/SNI handling. The primary mitigation is the existing threat model, not this
filter: scrapers are user-installed by definition (YAML uploads; Python scrapers
additionally need the typed confirmation and the pyScrapers setting) — only run
scrapers you trust. True network-level isolation means a sandboxed subprocess,
already tracked in PATCHES.md "Known limits / next steps". Redirect hops, by
contrast, ARE fully re-validated: see safe_get().
"""
import socket
import ipaddress
from urllib.parse import urlparse, urljoin


def safe_image_url(url: str) -> bool:
    """SSRF guard: public http(s) endpoints only.

    Rejects non-http schemes and hosts that resolve to loopback / private /
    link-local / reserved / multicast addresses, so a scraper result can't
    make the server fetch internal services (127.0.0.1, 169.254.169.254, …)."""
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        infos = socket.getaddrinfo(p.hostname, p.port or
                                   (443 if p.scheme == "https" else 80))
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


MAX_REDIRECTS = 3
_REDIRECT_STATUS = {301, 302, 303, 307, 308}


def safe_get(session, url, **kw):
    """GET that re-validates every redirect hop against safe_image_url.

    Redirects are fetched manually (allow_redirects=False): each Location is
    resolved relative to the current URL, must keep an http(s) scheme without a
    https→http downgrade, and must pass safe_image_url before it is followed.
    Raises ValueError on a blocked hop or when MAX_REDIRECTS is exceeded, so a
    redirect chain can never reach a private host. **kw (timeout, headers, …)
    passes through untouched. Call sites should still pre-check the entry URL —
    the pre-check catches the obvious case cheaply; this catches the rest."""
    kw["allow_redirects"] = False
    hops = MAX_REDIRECTS
    while True:
        r = session.get(url, **kw)
        if r.status_code not in _REDIRECT_STATUS:
            return r
        if hops <= 0:
            raise ValueError(f"blocked unsafe redirect: more than {MAX_REDIRECTS} hops from {url[:80]}")
        loc = r.headers.get("Location") or ""
        if not loc:
            raise ValueError(f"blocked unsafe redirect: missing Location from {url[:80]}")
        nxt = urljoin(url, loc)
        if not safe_image_url(nxt):
            raise ValueError(f"blocked unsafe redirect to {nxt[:80]}")
        if urlparse(url).scheme == "https" and urlparse(nxt).scheme != "https":
            raise ValueError(f"blocked unsafe redirect: https→http downgrade to {nxt[:80]}")
        url = nxt
        hops -= 1
