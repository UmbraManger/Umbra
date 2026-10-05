"""Brazzers scraper — uses Project1Service API."""
import json, sys
import p1api

SITE_URL = "https://www.brazzers.com"
STUDIO = "Brazzers"


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
    """Scrape performer page via HTML (API may not have dedicated endpoint)."""
    try:
        import cloudscraper
        from lxml import html as lxml_html
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=15)
        resp.raise_for_status()
        tree = lxml_html.fromstring(resp.text)
        name = (tree.xpath('//h1/text()') or [None])[0]
        if name:
            name = name.strip()
        image = (tree.xpath('//meta[@property="og:image"]/@content') or [None])[0]
        return {'kind': 'performer', 'name': name, 'photo': image, 'image': image, 'url': url}
    except Exception as e:
        return {'error': str(e), 'notFound': True}


def _search_performer(query):
    """Search for performer via API actors endpoint."""
    try:
        data = p1api.api_get('/v2/actors', {'search': query, 'limit': 10}, site_url=SITE_URL)
        if isinstance(data, list):
            for actor in data:
                if isinstance(actor, dict) and actor.get('name'):
                    p = {'kind': 'performer', 'name': actor['name'].strip()}
                    if actor.get('customUrl'):
                        p['url'] = f"{SITE_URL}/pornstar/{actor['customUrl']}"
                    return p
    except Exception:
        pass
    return {'notFound': True}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python brazzers_scraper.py <search|url> <query_or_url>')
        sys.exit(1)
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'search':
        print(json.dumps(p1api.search(arg, SITE_URL, STUDIO), indent=2))
    elif op == 'url':
        print(json.dumps(p1api.scene_by_url(arg, SITE_URL, STUDIO), indent=2))
    else:
        print(json.dumps({'error': f'Unknown op: {op}'}))
