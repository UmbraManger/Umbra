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


def release_to_scene(release, default_studio="Unknown"):
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
        if actor.get('customUrl'):
            p['url'] = f"https://www.brazzers.com/pornstar/{actor['customUrl']}"
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
        scene = release_to_scene(rel, default_studio)
        if scene.get('title'):
            results.append(scene)
    return results[:limit] if results else {'notFound': True}


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
        return release_to_scene(data, default_studio)
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
