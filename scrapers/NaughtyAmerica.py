"""NaughtyAmerica scraper — page HTML/JSON-LD (no public search API).
Scene URLs (…/scene/{slug}-{id}) and /pornstar/{slug} profiles.
Scene search goes through the sitemap index (NA's search page is a JS app);
performer lookup by name guesses the URL slug, so names that don't map to a
profile come back notFound."""
import json, re, sys, time
import requests
from bs4 import BeautifulSoup

SITE_URL = "https://www.naughtyamerica.com"
STUDIO = "Naughty America"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
           'Accept-Language': 'en-US,en;q=0.9'}


def _get(url, retries=2):
    """NA serves 202/empty when throttling; short polite retry."""
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=(15, 30))
        except Exception as e:
            return {'error': str(e)}
        if r.status_code == 200 and r.text:
            return BeautifulSoup(r.text, 'html.parser')
        time.sleep(5 * (i + 1))
    return {'error': f'HTTP {r.status_code} — rate limited, try again shortly'}


def _ld(soup, ltype):
    """First ld+json block whose @type matches."""
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            j = json.loads(s.get_text())
        except Exception:
            continue
        if j.get('@type') == ltype:
            return j
    return {}


def _minute(soup):
    el = soup.select_one('.duration')
    txt = (el.get_text(' ', strip=True) if el else '').replace('|', ' ')
    num = re.search(r'(\d+)', txt)
    return int(num.group(1)) if num else None


def _scene(url):
    soup = _get(url)
    if isinstance(soup, dict):
        return {'notFound': True, **soup}
    j = _ld(soup, 'VideoObject')
    scene = {'kind': 'scene'}
    scene['title'] = (j.get('name') or '').strip()
    if not scene['title']:
        return {'notFound': True, 'url': url}
    if j.get('description'):
        scene['details'] = j['description'].strip()
    img = j.get('thumbnailUrl')
    if isinstance(img, list):
        img = next((s for s in img if isinstance(s, str)), None)
    if isinstance(img, str) and img.startswith('http'):
        scene['image'] = scene['thumbnail'] = scene['cardThumbnail'] = scene['cover_a'] = scene['cover_b'] = img
    date = (j.get('uploadDate') or '')[:10]
    if re.match(r'\d{4}-\d{2}-\d{2}', date):
        scene['date'] = date
    dur = _minute(soup)
    if dur:
        scene['duration_min'] = dur
    m = re.search(r'-(\d+)(?:\?|$|/)', url) or re.search(r'custom1=(\d+)', url)
    if m:
        scene['code'] = m.group(1)
    G = {'female': 'f', 'male': 'm', 'transgender': 't'}
    scene['performers'] = []
    for a in (j.get('actor') or []):
        if isinstance(a, dict) and a.get('name'):
            p = {'name': a['name'].strip()}
            g = G.get((a.get('gender') or '').strip().lower())
            if g:
                p['gender'] = g
            scene['performers'].append(p)
    studio_el = soup.select_one('a[href*="/site/"][class*="site-title"]')
    studio = studio_el.get_text(' ', strip=True) if studio_el else STUDIO
    if studio:
        scene['studio'] = studio
        scene['groups'] = [{'name': studio}]
    scene['tags'] = []
    for a in soup.select('a[href*="/fantasy/"]'):
        t = a.get_text(' ', strip=True)
        if t and t.lower() not in ('remastered hd',) and t not in scene['tags']:
            scene['tags'].append(t)
    return scene


def _performer(url):
    soup = _get(url)
    if isinstance(soup, dict):
        return {'notFound': True, **soup}
    j = _ld(soup, 'Person')
    name = (j.get('name') or '').strip()
    if not name:
        return {'notFound': True, 'url': url}
    perf = {'kind': 'performer', 'name': name}
    img = j.get('image')
    if isinstance(img, list):
        img = next((s for s in img if isinstance(s, str)), None)
    if isinstance(img, str) and img.startswith('http'):
        perf['photo'] = perf['image'] = img
    if j.get('description'):
        perf['bio'] = j['description']
    if (j.get('gender') or '').lower() == 'female':
        perf['gender'] = 'f'
    elif (j.get('gender') or '').lower() == 'male':
        perf['gender'] = 'm'
    if j.get('url'):
        perf['url'] = j['url']
    return perf


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')


_SCENE_INDEX = []


def _scene_index(max_sitemaps=6):
    """Every NA scene URL, read from the sitemap index.

    NA's search page is a client-side app (no server-rendered results), but the
    sitemap index lists every scene URL with its title in the slug — the only
    index that can actually be queried. Capped per session so one search does
    not re-walk all 27 sitemaps.
    """
    global _SCENE_INDEX
    if _SCENE_INDEX:
        return _SCENE_INDEX
    soup = _get(f'{SITE_URL}/sitemap.xml')
    if isinstance(soup, dict):
        return []
    loc = r'<loc>\s*([^<\s]+)\s*</loc>'
    urls = []
    maps = [m for m in re.findall(loc, str(soup)) if '/scene' in m][:max_sitemaps]
    for m in maps:
        s = _get(m)
        if isinstance(s, dict):
            continue
        urls += re.findall(loc, str(s))
    _SCENE_INDEX = urls
    return urls


def _search_scene(title):
    """Best sitemap match for a scene title."""
    qtok = [t for t in re.split(r'[^a-z0-9]+', (title or '').lower()) if len(t) > 1]
    if not qtok:
        return {'notFound': True}
    need = -(-len(qtok) * 7 // 10)          # ~70% of the query tokens
    best, best_score = None, 0
    for u in _scene_index():
        stok = set(re.split(r'[^a-z0-9]+', u.rsplit('/', 1)[-1].lower()))
        score = sum(1 for t in qtok if t in stok)
        if score > best_score:
            best, best_score = u, score
    if not best or best_score < need:
        return {'notFound': True,
                'error': f'no scene matching {title!r} in the sitemap index'}
    return _scene(best)


def scrape(title="", url="", html="", kind="", **kwargs):
    if url:
        if '/pornstar/' in url:
            return _performer(url)
        if '/scene/' in url or re.search(r'-\d+$', url):
            return _scene(url)
        return {'notFound': True, 'url': url}
    if title:
        if kind == 'performer':
            return _performer(f'{SITE_URL}/pornstar/{_slug(title)}')
        return _search_scene(title)
    return {}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python NaughtyAmerica.py <scene|perf|name> <url_or_name>')
        sys.exit(1)
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'scene':
        print(json.dumps(_scene(arg), indent=2))
    elif op in ('perf', 'name'):
        print(json.dumps(_performer(arg) if '/' in arg
                         else _performer(f'{SITE_URL}/pornstar/{_slug(arg)}'), indent=2))
    else:
        print(json.dumps({'error': f'Unknown op: {op}'}))
