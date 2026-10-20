"""NaughtyAmerica scraper — page HTML/JSON-LD (no public search API).
Scene URLs (…/scene/{slug}-{id}) and /pornstar/{slug} profiles.
NA has no scannable search page (JS app behind Cloudflare) and serves 202 to
cold requests, so title/performer search walks the public sitemap catalog once
and caches it next to this scraper; lookups then run offline and instantly."""
import json, os, re, sys, time
from datetime import date, timedelta
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


_CAT = None


def _cat_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'naughtyamerica.index.json')


def _index():
    """{'scenes': [...urls], 'performers': [...urls]} — sitemap catalog cached
    on disk for 30 days. One walk takes a few quiet minutes (NA throttles), so
    it happens once; never memoized on failure so a throttled run retries."""
    global _CAT
    if _CAT is not None:
        return _CAT
    try:
        with open(_cat_path(), encoding='utf-8') as f:
            d = json.load(f)
        if d.get('scenes') and date.today() - date.fromisoformat(d['built'][:10]) <= timedelta(days=30):
            _CAT = d
            return d
    except Exception:
        pass
    _CAT = _build_index()
    return _CAT


def _build_index():
    loc = re.compile(r'<loc>\s*([^<\s]+)\s*</loc>')
    soup = _get(f'{SITE_URL}/sitemap.xml')
    if isinstance(soup, dict):
        return {}
    found = {}
    seen = set()
    for m in (u for u in re.findall(loc, str(soup)) if '/scene' in u or 'pornstar' in u):
        time.sleep(2)                        # NA 202s bursts of page fetches
        s = _get(m)
        if isinstance(s, dict):
            continue
        for u in re.findall(loc, str(s)):
            if u in seen:
                continue
            seen.add(u)
            if '/scene/' in u:
                found.setdefault('scenes', []).append(u)
            elif '/pornstar/' in u:
                found.setdefault('performers', []).append(u)
    if 'scenes' not in found:                # whole walk throttled — don't
        return {}                            # persist an empty catalog
    d = {'built': date.today().isoformat(), **found}
    try:
        with open(_cat_path(), 'w', encoding='utf-8') as f:
            json.dump(d, f)
    except OSError:
        pass
    return d


def _match(urls, title):
    """URL whose last slug shares the most query tokens; exact token beats
    4-char stem (so 'tits' hits 'tit', but a 'play' stem only half-counts and
    the slug with the literal word still wins)."""
    qtok = [t for t in re.split(r'[^a-z0-9]+', (title or '').lower()) if len(t) > 1]
    if not qtok or not urls:
        return None
    need = len(qtok) * 0.6                   # ~60% of the query tokens
    best, best_score = None, 0.0
    for u in urls:
        stok = set(re.split(r'[^a-z0-9]+', u.rsplit('/', 1)[-1].split('.')[0].lower()))
        score = sum(1.0 if q in stok else 0.5 if len(q) > 3 and
                    any(len(s) > 3 and s[:4] == q[:4] for s in stok) else 0.0
                    for q in qtok)
        if score > best_score or (score == best_score and best and len(u) < len(best)):
            best, best_score = u, score
    return best if best_score >= need else None


def _search_scene(title):
    best = _match(_index().get('scenes', []), title)
    if not best:
        return {'notFound': True,
                'error': f'no scene matching {title!r} in the sitemap catalog'}
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
            u = _match(_index().get('performers', []), title)
            return _performer(u or f'{SITE_URL}/pornstar/{_slug(title)}')
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
