"""Brazzers scraper — uses Project1Service API (v1)."""
import json, re, sys
import p1api

SITE_URL = "https://www.brazzers.com"
STUDIO = "Brazzers"
GENDER = {'female': 'f', 'male': 'm', 'transgender': 't', 'trans': 't'}


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


def _actor_img(actor):
    """Best profile photo: profile images come sized lg > md > sm > xs."""
    prof = ((actor.get('images') or {}).get('profile') or {})
    for v in prof.values():
        if isinstance(v, dict):
            for size in ('lg', 'md', 'sm', 'xs'):
                if isinstance(v.get(size), dict) and v[size].get('url'):
                    return v[size]['url']
    return p1api.get_best_image(actor.get('images') or {})

def _actor_to_perf(actor, url=""):
    """Project1Service/actors v1 object → Umbra performer dict."""
    perf = {'kind': 'performer', 'name': (actor.get('name') or '').strip()}
    g = GENDER.get((actor.get('gender') or '').strip().lower())
    if g:
        perf['gender'] = g
    if actor.get('bio'):
        perf['bio'] = actor['bio']
    if actor.get('birthday'):
        perf['birth'] = p1api.parse_date(actor['birthday'])
    if actor.get('birthPlace'):
        perf['nationality'] = actor['birthPlace']
    if actor.get('height'):
        # API ships inches for US sites (62 = 5'2") — cm is what the form keeps
        h = actor['height'] if isinstance(actor['height'], (int, float)) else int(str(actor['height'])[:3])
        perf['height'] = int(round(h * 2.54)) if h <= 100 else int(h)
    if actor.get('weight'):
        perf['weight'] = int(actor['weight'])
    if actor.get('measurements'):
        perf['measurements'] = actor['measurements']
    aliases = [a.strip() for a in (actor.get('aliases') or []) if a and a.strip()]
    if aliases:
        perf['aliases'] = ', '.join(aliases)
    img = _actor_img(actor)
    if img:
        perf['photo'] = img
        perf['image'] = img
    if url:
        perf['url'] = url
    return perf

def _performer(url):
    """Actor detail via the API (the /pornstar/{id}/{slug} URL carries the id);
    falls back to the HTML page for hand-typed ids the API doesn't know."""
    m = re.search(r'/(?:pornstar|model)/(\d+)', url)
    if m:
        try:
            res = p1api.api_get(f'/v1/actors/{m.group(1)}', None, site_url=SITE_URL).get('result')
            if isinstance(res, list) and res:
                res = res[0]
            if isinstance(res, dict) and res.get('name'):
                return _actor_to_perf(res, url)
        except Exception:
            pass
    return _performer_html(url)


def _performer_html(url):
    """HTML fallback (API may not know the actor id)."""
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
    """Search for performer via the API actors endpoint."""
    try:
        res = p1api.api_get('/v1/actors', {'search': query, 'limit': 10}, site_url=SITE_URL).get('result') or []
        for actor in res:
            if isinstance(actor, dict) and actor.get('name'):
                url = ""
                if actor.get('id') and actor.get('customUrl'):
                    url = f"{SITE_URL}/pornstar/{actor['id']}/{actor['customUrl']}"
                return _actor_to_perf(actor, url)
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
