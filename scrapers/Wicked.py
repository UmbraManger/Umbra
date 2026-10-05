"""Wicked scraper — uses Algolia API."""
import json, sys
import algolia

SITE_URL = "https://www.wicked.com"
REFERER = "https://www.wicked.com/"


def scrape(title="", url="", html="", kind="", **kwargs):
    if url:
        return algolia.scene_by_url(url, SITE_URL, REFERER)
    if title:
        results = algolia.search_scenes(title, SITE_URL, REFERER)
        if isinstance(results, list) and results:
            return results[0]
        return results
    return {}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python Wicked.py <search|url> <query_or_url>')
        sys.exit(1)
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'search':
        print(json.dumps(algolia.search_scenes(arg, SITE_URL, REFERER), indent=2))
    elif op == 'url':
        print(json.dumps(algolia.scene_by_url(arg, SITE_URL, REFERER), indent=2))
    else:
        print(json.dumps({'error': f'Unknown op: {op}'}))
