"""Mofos scraper — uses Project1Service API.
Sites: mofos.com, iknowthatgirl.com"""
import json, re, sys
import p1api

SITE_URL = "https://www.mofos.com"
STUDIO = "Mofos"


def scrape(title="", url="", html="", kind="", **kwargs):
    if url:
        if '/pornstar/' in url or '/model/' in url:
            return _performer(url)
        return p1api.scene_by_url(url, SITE_URL, STUDIO)
    if title:
        if kind == 'performer':
            return _search_performer(title)
        results = p1api.search(title, SITE_URL, STUDIO)
        if isinstance(results, list) and results:
            return results[0]
        return results
    return {}


def _performer(url):
    m = re.search(r'/(?:pornstar|model)/(\d+)', url)
    if m:
        try:
            actor = p1api.actor_get(m.group(1), SITE_URL)
            if actor:
                return p1api.actor_to_perf(actor, SITE_URL, url)
        except Exception:
            pass
    return {'notFound': True, 'url': url}


def _search_performer(query):
    actor = p1api.actor_search(query, SITE_URL)
    if actor:
        return p1api.actor_to_perf(actor, SITE_URL, p1api.actor_url(actor, SITE_URL))
    return {'notFound': True}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python Mofos.py <search|url> <query_or_url>')
        sys.exit(1)
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'search':
        print(json.dumps(p1api.search(arg, SITE_URL, STUDIO), indent=2))
    elif op == 'url':
        print(json.dumps(p1api.scene_by_url(arg, SITE_URL, STUDIO), indent=2))
    else:
        print(json.dumps({'error': f'Unknown op: {op}'}))
