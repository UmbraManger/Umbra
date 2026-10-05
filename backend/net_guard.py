"""Shared SSRF guard for outbound fetches (server image downloads, scrapers)."""
import socket
import ipaddress
from urllib.parse import urlparse


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
