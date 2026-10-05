#!/usr/bin/env python3
"""Pornbox scraper v2 – field mappings verified against real /store/search JSON.

Key fixes vs v1:
  1. Query is URL-encoded (quote_plus) — v1 sent raw spaces/& and the query got
     mangled ("Bbc20Tall20..." → literal 20s), so strict search found nothing.
  2. Reads content.strict_contents FIRST — these are the exact-match hits
     (the site's "maybe you're looking for" suggestion). v1 read only
     content.contents (fuzzy 'relevant' matches) and returned results[0],
     which is usually a completely different scene.
  3. Best-match scoring for fuzzy results instead of blindly taking the first.
  4. Content-Type is checked before resp.json() (Cloudflare/HTML pages no longer
     crash parsing silently).
  5. Field names mapped to the verified schema:
       title       -> scene_name (fallback customName)
       date        -> publish_date "2022-08-24T22:00:00.000Z"
       thumbnail   -> thumbnail.large (thumbnail is a dict)
       performers  -> models[].model_name / .sex (+ male_models if present)
       tags        -> niches[].niche
       studio      -> studio (plain string) or studios[].name (type == 'main')
  6. Scene id extraction from HTML removed — the page is an SPA shell whose
     inline templates contain unrelated "id": values.
"""
import json
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import quote_plus

import cloudscraper

scraper = cloudscraper.create_scraper()
BASE_URL = 'https://www.pornbox.com'
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 30


# ---------------------------------------------------------------- helpers
def _fetch(url, attempts=3):
    """Fetch URL, ensure JSON, with retry + backoff."""
    last_err = None
    for i in range(attempts):
        try:
            resp = scraper.get(
                url,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                headers={'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
            )
            resp.raise_for_status()
            ctype = resp.headers.get('Content-Type', '')
            if 'json' not in ctype:
                raise ValueError(f'non-JSON response ({ctype}): {resp.text[:120]!r}')
            return resp.json()
        except Exception as e:
            last_err = e
            if i < attempts - 1:
                import time
                time.sleep(1.5 * (i + 1))
    raise last_err


def _parse_date(raw):
    """'2022-08-24T22:00:00.000Z' -> '2022-08-24'."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        try:
            return datetime.strptime(str(raw)[:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d')
        except Exception:
            return raw


def _format_display_date(iso_str):
    """'2022-08-24' -> 'August 24, 2022'."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        return f"{months[dt.month - 1]} {dt.day}, {dt.year}"
    except Exception:
        return iso_str


def _pick_thumbnail(item):
    """thumbnail is a dict {list, small, large, mosaic}; tolerate a plain string too."""
    t = item.get('thumbnail')
    if isinstance(t, dict):
        return t.get('large') or t.get('list') or t.get('small') or ''
    return t or item.get('player_poster') or ''


def _title_score(a, b):
    norm = lambda s: re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


# ---------------------------------------------------------------- search
def search_scenes(query):
    """Search; returns exact (strict) matches first, then fuzzy 'relevant' ones."""
    url = f'{BASE_URL}/store/search?q={quote_plus(query)}&skip=0'
    data = _fetch(url)
    content = data.get('content') or {}
    results = []

    # 1) exact matches = the site's "maybe you're looking for" suggestion
    for item in content.get('strict_contents') or []:
        sid = item.get('source_id') or item.get('id')
        results.append({
            'kind': item.get('type', 'scene'),
            'title': item.get('name', ''),
            'url': f'{BASE_URL}/contents/{sid}',
            'thumbnail': '',
            'cardThumbnail': '',
            'date': None,
            'releaseDate': None,
            'id': sid,
            'strict': True,
        })

    # 2) fuzzy matches
    for item in content.get('contents') or []:
        iso_date = _parse_date(item.get('publish_date'))
        thumb = _pick_thumbnail(item)
        sid = item.get('content_id') or item.get('id')
        results.append({
            'kind': 'scene',
            'title': item.get('scene_name') or item.get('customName', ''),
            'url': f'{BASE_URL}/contents/{sid}',
            'thumbnail': thumb,
            'cardThumbnail': thumb,
            'cover_a': thumb,
            'cover_b': thumb,
            'date': iso_date,
            'releaseDate': _format_display_date(iso_date),
            'id': sid,
            'strict': False,
        })
    return results


# ---------------------------------------------------------------- scene
def scrape_scene(url_or_id):
    """Scrape a single scene by id or URL (URL must contain a numeric id)."""
    s = str(url_or_id)
    m = re.search(r'/(?:contents|watch-page|model|niche)/(\d+)', s)
    if m:
        scene_id = m.group(1)
    elif s.isdigit():
        scene_id = s
    else:
        return {'error': 'Could not extract scene ID', 'url': url_or_id,
                'hint': 'SPA page HTML contains no usable id; pass the numeric id or a /contents/<id> URL'}

    data = _fetch(f'{BASE_URL}/contents/{scene_id}')

    iso_date = _parse_date(data.get('publish_date'))

    tags = [n.get('niche') for n in (data.get('niches') or []) if n.get('niche')]

    performers = []
    for model in (data.get('models') or []) + (data.get('male_models') or []):
        name = model.get('model_name', '')
        if name:
            performers.append({'name': name, 'gender': model.get('sex', '')})

    studio = data.get('studio', '')
    if isinstance(studio, dict):
        studio = studio.get('name', '')
    if not studio:
        for st in data.get('studios') or []:
            if st.get('type') == 'main':
                studio = st.get('name', '')
                break
        if not studio and data.get('studios'):
            studio = data['studios'][0].get('name', '')

    image = data.get('player_poster') or _pick_thumbnail(data)

    return {
        'kind': 'scene',
        'title': data.get('scene_name') or data.get('customName', ''),
        'date': iso_date,
        'releaseDate': _format_display_date(iso_date),
        'details': data.get('small_description') or data.get('description', ''),
        'studio': studio,
        'performers': performers,
        'tags': tags,
        'image': image,
        'thumbnail': image,
        'cardThumbnail': image,
        'cover_a': image,
        'cover_b': image,
        'url': f'{BASE_URL}/application/watch-page/{scene_id}',
        'id': scene_id,
    }


# ---------------------------------------------------------------- entry
def scrape(title="", url="", html="", name="", **kwargs):
    """Unified entry point called by the backend."""
    if url:
        return scrape_scene(url)
    query = (title or name or "").strip()
    if not query:
        return {'error': 'need url or title', 'notFound': True}

    results = search_scenes(query)
    if not results:
        return {'notFound': True, 'query': query}

    # exact match first, else best fuzzy title match, else best guess
    strict = [r for r in results if r.get('strict')]
    if strict:
        best = strict[0]
    else:
        best = max(results, key=lambda r: _title_score(query, r['title']))
        if _title_score(query, best['title']) < 0.5:
            return {'notFound': True, 'query': query,
                    'candidates': [{'title': r['title'], 'id': r['id']} for r in results[:5]]}

    detail = scrape_scene(str(best['id']))
    detail['matchScore'] = round(_title_score(query, best['title']), 3)
    detail['strictMatch'] = bool(best.get('strict'))
    return detail


def main():
    if len(sys.argv) < 3:
        print('Usage: python pornbox_scraper_fixed.py <search|scene> <query_or_url_or_id>')
        sys.exit(1)
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'search':
        print(json.dumps(search_scenes(arg), indent=2))
    elif op == 'scene':
        print(json.dumps(scrape_scene(arg), indent=2))
    else:
        print(f'Unknown operation: {op}')
        sys.exit(1)


if __name__ == '__main__':
    main()
