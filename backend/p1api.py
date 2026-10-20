"""Shared Project1Service API client for Aylo/MG Premium sites.

Used by: Brazzers, DigitalPlayground, FakeHub, Mofos, RealityKings, etc.
API: https://site-api.project1service.com
"""
import re
import requests as req

API_BASE = "https://site-api.project1service.com"
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 30

# Instance tokens cached per domain
_tokens = {}


def _get_instance_token(site_url):
    """Fetch instance_token from a site's cookies."""
    if site_url in _tokens:
        return _tokens[site_url]
    try:
        r = req.get(site_url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })
        r.raise_for_status()
        tok = r.cookies.get('instance_token')
        if tok:
            _tokens[site_url] = tok
            return tok
        # Fallback: some stacks only surface it in the raw Set-Cookie header.
        m = re.search(r'instance_token=([^;,\s]+)', r.headers.get('set-cookie', ''))
        if m:
            _tokens[site_url] = m.group(1)
            return m.group(1)
    except Exception:
        pass
    return None


def api_get(path, params=None, site_url="https://www.brazzers.com"):
    """Make an authenticated GET request to the P1 API."""
    token = _get_instance_token(site_url)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
    }
    if token:
        headers['Instance'] = token
    url = f"{API_BASE}{path}"
    r = req.get(url, params=params, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    if r.status_code in (401, 403) and token:
        _tokens.pop(site_url, None)
        token = _get_instance_token(site_url)
        if token:
            headers['Instance'] = token
            r = req.get(url, params=params, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    r.raise_for_status()
    return r.json()


def parse_date(raw):
    """Parse various date formats into ISO."""
    if not raw:
        return None
    raw = raw.strip().replace('Z', '+00:00')
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(raw)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        pass
    from datetime import datetime
    for fmt in ('%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return raw[:10] if len(raw) >= 10 else raw


def get_best_image(images_dict):
    """Extract best image URL from P1 API images object.

    images.poster -> {"0": {xs: {url}, sm: {url}, md: {url}, lg: {url}}}
    """
    if not isinstance(images_dict, dict):
        return None
    poster = images_dict.get('poster', {})
    if isinstance(poster, dict):
        for size_group in poster.values():
            if isinstance(size_group, dict):
                for size_key in ('lg', 'md', 'sm', 'xs'):
                    size_data = size_group.get(size_key, {})
                    if isinstance(size_data, dict) and size_data.get('url'):
                        return size_data['url']
    # Fallback: try thumbnail, cover keys
    for key in ('thumbnail', 'cover', 'image'):
        val = images_dict.get(key)
        if isinstance(val, str) and val.startswith('http'):
            return val
        if isinstance(val, dict):
            for size_key in ('lg', 'md', 'sm', 'xs'):
                sub = val.get(size_key, {})
                if isinstance(sub, dict) and sub.get('url'):
                    return sub['url']
    return None


def release_to_scene(release, default_studio="Unknown", site_url="https://www.brazzers.com"):
    """Convert a P1 API release object to Umbra scene dict."""
    scene = {'kind': 'scene'}

    scene['title'] = (release.get('title') or '').strip()

    date_str = release.get('dateReleased', '')
    if date_str:
        scene['date'] = parse_date(date_str)

    desc = release.get('description', '')
    if desc:
        scene['details'] = desc.strip()

    scene_id = release.get('id')
    if scene_id:
        scene['code'] = str(scene_id)

    # Duration (seconds -> minutes)
    duration_sec = release.get('duration', 0)
    if duration_sec:
        scene['duration_min'] = int(duration_sec) // 60

    # Performers
    performers = []
    for actor in release.get('actors', []):
        p = {}
        if actor.get('name'):
            p['name'] = actor['name'].strip()
        if actor.get('gender'):
            p['gender'] = actor['gender'].strip()
        if actor.get('id'):
            p['url'] = f"{site_url}/pornstar/{actor['customUrl'] or actor['id']}"
        if actor.get('id'):
            p['id'] = str(actor['id'])
        if p.get('name'):
            performers.append(p)
    scene['performers'] = performers

    # Tags
    tags = []
    for tag in release.get('tags', []):
        if isinstance(tag, dict) and tag.get('name'):
            tags.append(tag['name'].strip())
        elif isinstance(tag, str):
            tags.append(tag.strip())
    scene['tags'] = tags

    # Studio
    studio = None
    collections = release.get('collections', [])
    if collections:
        col = collections[0]
        if isinstance(col, dict):
            studio = col.get('name', '').strip()
    if not studio:
        brand = release.get('brand', {})
        if isinstance(brand, dict):
            studio = brand.get('name', '').strip()
        elif isinstance(brand, str):
            studio = brand.strip()
    scene['studio'] = studio or default_studio

    # Groups (movies/series)
    groups = []
    for group in release.get('groups', []):
        if isinstance(group, dict) and group.get('name'):
            groups.append({'name': group['name'].strip()})
    if groups:
        scene['groups'] = groups

    # Image
    image = get_best_image(release.get('images', {}))
    if image:
        scene['image'] = image
        scene['thumbnail'] = image
        scene['cardThumbnail'] = image
        scene['cover_a'] = image
        scene['cover_b'] = image

    return scene


def search(query, site_url="https://www.brazzers.com", default_studio="Unknown", limit=15):
    """Search via P1 API."""
    try:
        data = api_get('/v2/releases', {'search': query, 'limit': limit}, site_url=site_url)
    except Exception as e:
        return {'error': str(e), 'notFound': True}

    releases = []
    if isinstance(data, list):
        releases = data
    elif isinstance(data, dict):
        releases = data.get('result', data.get('results', data.get('releases', data.get('data', []))))

    if not releases:
        return {'notFound': True, 'query': query}

    results = []
    for rel in releases:
        scene = release_to_scene(rel, default_studio, site_url)
        if scene.get('title'):
            results.append(scene)
    if results:
        import titlematch
        results.sort(key=lambda s: titlematch.coverage(query, s.get('title')), reverse=True)
        return results[:limit]
    return {'notFound': True}


def get_scene(scene_id, site_url="https://www.brazzers.com", default_studio="Unknown"):
    """Fetch single scene by ID."""
    try:
        data = api_get(f'/v2/releases/{scene_id}', site_url=site_url)
    except Exception as e:
        return {'error': str(e), 'notFound': True}
    # Detail endpoints wrap the release in {"meta": ..., "result": {...}}
    if isinstance(data, dict) and isinstance(data.get('result'), dict):
        data = data['result']
    if isinstance(data, dict) and data.get('title'):
        return release_to_scene(data, default_studio, site_url)
    return {'notFound': True, 'scene_id': scene_id}


def scene_by_url(url, site_url="https://www.brazzers.com", default_studio="Unknown"):
    """Extract scene from URL (tries to find scene ID)."""
    m = re.search(r'/scene/(?:view/)?(\d+)', url)
    if m:
        return get_scene(m.group(1), site_url, default_studio)
    m = re.search(r'/(\d+)(?:/|$)', url)
    if m:
        return get_scene(m.group(1), site_url, default_studio)
    return {'error': 'Could not extract scene ID from URL', 'notFound': True}


# ---- shared performers (v1/actors works for every P1 site) ----
GENDER = {'female': 'f', 'male': 'm', 'transgender': 't', 'trans': 't'}


def actor_to_perf(actor, site_url="https://www.brazzers.com", url=""):
    """Project1Service /v1/actors object → Umbra performer dict."""
    perf = {'kind': 'performer', 'name': (actor.get('name') or '').strip()}
    g = GENDER.get((actor.get('gender') or '').strip().lower())
    if g:
        perf['gender'] = g
    if actor.get('bio'):
        perf['bio'] = actor['bio']
    if actor.get('birthday'):
        perf['birth'] = parse_date(actor['birthday'])
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


def _actor_img(actor):
    """Best profile photo: profile images come sized lg > md > sm > xs."""
    prof = ((actor.get('images') or {}).get('profile') or {})
    for v in prof.values():
        if isinstance(v, dict):
            for size in ('lg', 'md', 'sm', 'xs'):
                if isinstance(v.get(size), dict) and v[size].get('url'):
                    return v[size]['url']
    return get_best_image(actor.get('images') or {})


def actor_get(actor_id, site_url):
    """Actor detail by numeric id: the site's /pornstar/{id}/{slug} URL."""
    res = api_get(f'/v1/actors/{actor_id}', None, site_url=site_url).get('result')
    if isinstance(res, list) and res:
        res = res[0]
    return res if isinstance(res, dict) and res.get('name') else {}


def actor_url(actor, site_url):
    if actor.get('id') and actor.get('customUrl'):
        return f"{site_url}/pornstar/{actor['id']}/{actor['customUrl']}"
    if actor.get('id'):
        return f"{site_url}/pornstar/{actor['id']}"
    return ""


def actor_search(query, site_url):
    """Search the P1 actors endpoint; first hit with a name wins."""
    res = api_get('/v1/actors', {'search': query, 'limit': 10}, site_url=site_url).get('result') or []
    for actor in res:
        if isinstance(actor, dict) and actor.get('name'):
            return actor
    return {}
