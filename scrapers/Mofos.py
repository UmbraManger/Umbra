"""Mofos scraper — uses Project1Service API.
Sites: mofos.com, iknowthatgirl.com"""
import json, sys
import p1api

SITE_URL = "https://www.mofos.com"
STUDIO = "Mofos"


def scrape(title="", url="", html="", kind="", **kwargs):
    if url:
        return p1api.scene_by_url(url, SITE_URL, STUDIO)
    if title:
        results = p1api.search(title, SITE_URL, STUDIO)
        if isinstance(results, list) and results:
            return results[0]
        return results
    return {}


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
