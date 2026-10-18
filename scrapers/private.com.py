"""Private.com scraper — HTML structure mapping (no public API).
Scene URLs, search.php scene listings, and /pornstar/ profile pages."""
import json, re, sys
from urllib.parse import quote, urljoin
import requests
from bs4 import BeautifulSoup

SITE_URL = "https://www.private.com"
STUDIO = "Private"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
           'Accept-Language': 'en-US,en;q=0.9'}


def _soup(url):
    r = requests.get(url, headers=HEADERS, timeout=(15, 30))
    r.raise_for_status()
    return BeautifulSoup(r.text, 'html.parser')


def _search_performer(query):
    """private.com has no scrapable model search — find the name through its
    scene search (server-rendered search.php) and pull the profile link from
    the scene page's cast list (li.tag-models → name + /pornstar/ URL)."""
    qtok = set(t for t in re.findall(r'[a-z0-9]+', (query or '').lower()) if t)
    if not qtok:
        return {'notFound': True}
    try:
        scenes = _search_scenes(query)
    except Exception:
        scenes = []
    candidates = {}
    for s in (scenes if isinstance(scenes, list) else [])[:3]:
        try:
            soup = _soup(s['url'])
        except Exception:
            continue
        for a in soup.select('li.tag-models a'):
            name = a.get_text(' ', strip=True)
            if name and name not in candidates:
                candidates[name] = urljoin(SITE_URL, a.get('href', ''))
    match, match_len = None, 0
    for name in candidates:
        ntok = set(t for t in re.findall(r'[a-z0-9]+', name.lower()) if t)
        common = qtok & ntok
        # ≥ half of the profile's name tokens present in the query, and an
        # actual token overlap — filters unrelated cast names of other scenes
        if common and len(common) >= max(1, len(ntok) // 2) and len(ntok) > match_len:
            match, match_len = candidates[name], len(ntok)
    if not match:
        return {'notFound': True, 'error': f'no performer {query!r} found via private.com scene search'}
    return _performer(match)


def _min(soup):
    meta = soup.select_one('[itemprop="duration"]') or soup.select_one('meta[property="og:duration"]')
    raw = ((meta.get('content') or '') if meta else '').lower().strip()
    if not raw:
        return None
    try:                                      # '12:34', '1:02:12'
        parts = [int(x) for x in raw.replace(';', ':').split(':') if x.strip().isdigit()]
        if parts:
            h, m, s = ([0, 0] + parts)[-3:]
            return h * 60 + m + (1 if s >= 30 else 0) or 1
    except ValueError:
        pass
    h = re.search(r'(\d+)\s*h', raw)
    m = re.search(r'(\d+)\s*m(?:in)?(?![a-z])', raw)
    s = re.search(r'(\d+)\s*s(?:ec)?(?![a-z])', raw)
    if not (h or m or s):                     # 'PT31M54S', '75 min' handled by these
        return None
    total = (int(h.group(1)) if h else 0) * 60 + (int(m.group(1)) if m else 0) \
        + (1 if s and int(s.group(1)) >= 30 else 0)
    return total or 1


def _scene(url):
    r = requests.get(url, headers=HEADERS, timeout=(15, 30))
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    og = lambda p: (soup.select_one(f'meta[property="{p}"]') or {}).get('content')  # noqa: E731
    h1 = soup.select_one('h1')
    scene = {'kind': 'scene'}
    scene['title'] = (h1 and h1.get_text(' ', strip=True)) or (og('og:title') or '').strip()
    if not scene['title']:
        return {'notFound': True, 'url': url}
    date = (soup.select_one('[itemprop="uploadDate"], meta[property="article:published_time"]')
            or {}).get('content')
    if date:
        scene['date'] = date[:10]
    dur = _min(soup)
    if dur:
        scene['duration_min'] = dur
    desc = og('og:description')
    if desc:
        scene['details'] = desc.strip()
    img = og('og:image')
    if img:
        scene['image'] = img
        scene['thumbnail'] = img
        scene['cardThumbnail'] = img
        scene['cover_a'] = img
        scene['cover_b'] = img
    m = re.search(r'/scene/[^/]+/(\d+)', url)
    if m:
        scene['code'] = m.group(1)
    scene['performers'] = [{'name': a.get_text(' ', strip=True), 'url': urljoin(SITE_URL, a.get('href', ''))}
                           for a in soup.select('li.tag-models a') if a.get_text(' ', strip=True)]
    scene['tags'] = [a.get_text(' ', strip=True) for a in soup.select('li.tag-tags a')
                     if a.get_text(' ', strip=True)]
    site = soup.select_one('.title-site')
    scene['studio'] = (site and site.get_text(' ', strip=True)) or STUDIO
    groups = [{'name': scene['studio']}] if scene['studio'] else []
    if groups:
        scene['groups'] = groups
    return scene


def _facts(soup):
    out = {}
    for li in soup.select('ul.model-facts li'):
        em = li.select_one('em')
        v = ''.join(str(x) for x in li.contents if x.name != 'em').strip()
        if not em or not v or v == '-':
            continue
        out[em.get_text(' ', strip=True).rstrip(':').lower()] = v
    return out


def _performer(url):
    r = requests.get(url, headers=HEADERS, timeout=(15, 30))
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    og = lambda p: (soup.select_one(f'meta[property="{p}"]') or {}).get('content')  # noqa: E731
    h1 = soup.select_one('h1')
    name = (h1 and h1.get_text(' ', strip=True)) or ''
    if not name:
        return {'notFound': True, 'url': url}
    f = _facts(soup)
    f['hair'] = f.get('hair color', '')
    f['eyes'] = f.get('eye color', '')
    perf = {'kind': 'performer', 'name': name, 'gender': 'f'}
    if f.get('measurements'):
        perf['measurements'] = f['measurements']
    if f.get('height'):
        m = re.search(r'(\d+)\s*cm', f['height'])
        if m:
            perf['height'] = int(m.group(1))
    if f.get('weight'):
        m = re.search(r'(\d+)\s*kg', f['weight'])
        if m:
            perf['weight'] = int(m.group(1))
    for key in ('nationality', 'hair', 'eyes', 'tattoos', 'piercings'):
        if f.get(key):
            perf[key] = f[key]
    img = og('og:image')
    if img:
        perf['photo'] = img
    return perf


def _search_scenes(query):
    r = requests.get(f'{SITE_URL}/search.php?query={quote(query)}', headers=HEADERS,
                     timeout=(15, 30))
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    results, seen = [], set()
    for a in soup.select('a[href*="/scene/"]'):
        href = a.get('href', '') or ''
        title = a.get_text(' ', strip=True)
        # drop chip links ("4K") and <video> fallback text
        if not href or href in seen or len(title) < 5 or 'support the video' in title.lower():
            continue
        seen.add(href)
        results.append({'kind': 'scene', 'title': title, 'url': urljoin(SITE_URL, href)})
    return results


def scrape(title="", url="", html="", kind="", **kwargs):
    if url:
        try:
            if '/pornstar/' in url:
                return _performer(url)
            return _scene(url)
        except Exception as e:
            return {'notFound': True, 'error': str(e)}
    if title:
        try:
            if kind == 'performer':
                return _search_performer(title)
            results = _search_scenes(title)
        except Exception as e:
            return {'notFound': True, 'error': str(e)}
        if isinstance(results, list) and results:
            # rank by title fit, then fetch the detail page
            import algolia
            for s in results:
                s['_score'] = algolia.title_match_score(title, s['title'])
            results.sort(key=lambda s: s['_score'], reverse=True)
            for cand in results[:3]:
                if cand['_score'] <= 0:
                    break
                try:
                    return _scene(cand['url'])
                except Exception:
                    continue
            return results[0]
        return {'notFound': True}
    return {}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python private.com.py <search|url> <query_or_url>')
        sys.exit(1)
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'search':
        print(json.dumps(_search_scenes(arg), indent=2))
    elif op == 'url':
        out = _performer(arg) if '/pornstar/' in arg else _scene(arg)
        print(json.dumps(out, indent=2))
    else:
        print(json.dumps({'error': f'Unknown op: {op}'}))
