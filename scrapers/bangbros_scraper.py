#!/usr/bin/env python3
"""BangBros scraper – Aylo network sites (bangbros.com, sexselector.com, virtualporn.com).

Fixed:
- Description: extracted from <p> after "Description" h2
- Date: extracted from h2 containing "Month DD, YYYY" pattern
- Performers: limited to scene-header area (class sc-1b6bgon-*), excludes "Similar Videos"
- Tags: uses /videos/tags/ path
- Studio: uses /websites/ links
- Image: finds media-public*.project1content.com poster URLs via regex
"""
import json, re, sys
from datetime import datetime
from urllib.parse import quote, urljoin
import cloudscraper
from lxml import html as lxml_html

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)
scraper.headers.update({
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 30

SITES = ['bangbros.com', 'sexselector.com', 'virtualporn.com']


def _fetch(url, attempts=3):
    """Fetch URL with retry logic."""
    last_err = None
    for _ in range(attempts):
        try:
            resp = scraper.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_err = e
    raise last_err


def _format_display_date(iso_str):
    """Format ISO date as 'March 27, 2026'."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
        return f"{months[dt.month - 1]} {dt.day}, {dt.year}"
    except Exception:
        return iso_str


def _parse_date(raw):
    """Try to parse various date formats into ISO."""
    if not raw:
        return None
    raw = raw.strip()
    # Already ISO
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        pass
    for fmt in ('%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return raw


def _slug_to_title(url):
    """Convert URL slug to title. /video/12345/my-scene-name -> My Scene Name."""
    m = re.search(r'/video/\d+/(.+?)(?:\?|$)', url)
    if m:
        return m.group(1).replace('-', ' ').strip().title()
    return None


def _title_match_score(query, title):
    """Score how well a title matches the query. Higher = better match."""
    if not title or not query:
        return 0
    q = query.lower().strip()
    t = title.lower().strip()
    if q == t:
        return 100
    if q in t:
        return 90
    if t in q:
        return 80
    q_words = set(re.findall(r'\w+', q))
    t_words = set(re.findall(r'\w+', t))
    if not q_words or not t_words:
        return 0
    overlap = q_words & t_words
    stop = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'is', 'it', 'to', 'for', 'with', 'scene', 'ep', 'episode', 'date', 'part'}
    meaningful = overlap - stop
    if not meaningful:
        return 0
    q_meaningful = q_words - stop
    coverage = len(meaningful) / len(q_meaningful) if q_meaningful else 0
    if coverage < 0.5:
        return 0
    return int(coverage * 70)


def search_scenes(query):
    """Search BangBros.
    Note: BangBros search is JS-rendered and returns dead links.
    We scrape /videos listing pages for live scenes instead.
    Keeps paginating until a match is found or pages run out.
    """
    results = []
    seen = set()
    max_pages = 50

    for page in range(1, max_pages + 1):
        page_url = 'https://bangbros.com/videos' if page == 1 else f'https://bangbros.com/videos/page/{page}'
        try:
            resp = _fetch(page_url)
            tree = lxml_html.fromstring(resp.text)
        except Exception:
            break

        cards = tree.xpath('//a[contains(@href, "/video/")]')
        if not cards:
            break  # No more pages

        page_had_new = False
        for a in cards:
            href = a.get('href', '')
            if not href or href in seen:
                continue
            if '/video?' in href:
                continue
            seen.add(href)
            page_had_new = True
            href = urljoin('https://bangbros.com', href)

            title = a.get('title', '').strip()
            if not title:
                alt = a.xpath('.//img/@alt')
                if alt:
                    title = alt[0].strip()
            if not title:
                title = _slug_to_title(href) or ''
            if not title or len(title) < 3:
                continue

            thumbnail = ''
            img = a.xpath('.//img/@src')
            if not img:
                img = a.xpath('.//source/@srcset')
            if img:
                thumbnail = img[0].split(',')[0].strip().split(' ')[0]
                if thumbnail:
                    thumbnail = urljoin('https://bangbros.com', thumbnail)

            score = _title_match_score(query, title)
            entry = {
                'kind': 'scene', 'title': title, 'url': href, 'site': 'bangbros',
                'thumbnail': thumbnail, 'cardThumbnail': thumbnail,
                'cover_a': thumbnail, 'cover_b': thumbnail,
                '_match_score': score,
            }
            results.append(entry)

            # Good match found — return early
            if score > 0:
                results.sort(key=lambda r: r['_match_score'], reverse=True)
                return results

        if not page_had_new:
            break  # No new scenes, stop paginating

    results.sort(key=lambda r: r['_match_score'], reverse=True)
    return results if results else {'notFound': True}


def scrape_scene(url):
    """Scrape a single scene page.

    BangBros pages are server-rendered. Key selectors:
    - Title: <title> tag (strip suffix)
    - Description: <p> after <h2>Description</h2> (text "DescriptionCollapseExpand")
    - Date: <h2> containing "Month DD, YYYY" pattern
    - Performers: links to /model/ inside the scene-header area (class sc-1b6bgon-*),
      NOT the "Similar Videos" section (class one-list-*)
    - Tags: links to /videos/tags/
    - Studio: links to /websites/
    - Image: regex for media-public*.project1content.com poster URLs
    """
    url = urljoin('https://bangbros.com', url)
    resp = _fetch(url)
    tree = lxml_html.fromstring(resp.text)
    page_text = resp.text

    # ── Title ──────────────────────────────────────────────────────
    title = None
    title_tag = tree.xpath('//title/text()')
    if title_tag:
        t = title_tag[0].strip()
        # Strip site suffix like " | BangBros" or " Video"
        t = re.sub(r'\s*(Video|[-|]\s*Bang.*|\s*Porn.*|\s*Sex.*)\s*$', '', t, flags=re.I).strip()
        t = re.sub(r'\s+Video\s*$', '', t, flags=re.I).strip()
        if t and len(t) > 3:
            title = t
    if not title:
        title = _slug_to_title(url)

    # ── Description ────────────────────────────────────────────────
    # The description is in a <p> tag sibling of an <h2> whose text starts with "Description"
    # Note: h2 text is "DescriptionCollapseExpand" so contains(text(),...) may not match;
    # use text_content() check instead.
    details = None
    all_h2_for_desc = tree.xpath('//h2')
    for h2_el in all_h2_for_desc:
        if h2_el.text_content().strip().startswith('Description'):
            parent = h2_el.getparent()
            if parent is not None:
                p_tags = parent.xpath('.//p')
                if p_tags:
                    details = p_tags[0].text_content().strip()
            break

    # Fallback: try og:description
    if not details:
        og_desc = tree.xpath('//meta[@property="og:description"]/@content')
        if og_desc:
            details = og_desc[0].strip()

    # ── Image ──────────────────────────────────────────────────────
    # No og:image or poster attribute. Images are at
    # media-public*.project1content.com/*/poster/poster_01.jpg
    thumbnail = None
    imgs = re.findall(
        r'(https?://media[^\s"<>]+poster[^\s"<>]*\.(?:jpg|jpeg|png|webp))',
        page_text
    )
    if imgs:
        thumbnail = imgs[0]

    # ── Performers ─────────────────────────────────────────────────
    # Scene performers are in the scene-header area (class sc-1b6bgon-*).
    # The "Similar Videos" section (class one-list-*) also has model links we must exclude.
    performers = []
    seen_names = set()

    # Primary: get links from the scene-header performer container
    model_links = tree.xpath(
        '//div[contains(@class, "sc-1b6bgon")]//a[contains(@href, "/model/")]'
    )
    # Fallback: get ALL model links but stop when we hit the "Similar Videos" / "one-list-" section
    if not model_links:
        all_links = tree.xpath('//a[contains(@href, "/model/")]')
        model_links = []
        for a in all_links:
            # Check if this link is inside a "one-list-*" (similar videos) container
            ancestors = a.xpath('ancestor::div[contains(@class, "one-list")]')
            if ancestors:
                break  # Stop collecting — we've reached the similar videos section
            model_links.append(a)

    for a in model_links:
        name = a.text_content().strip()
        # Clean trailing commas and extra whitespace (e.g., "Roxanne Roselle,"", "Tony Marzo")
        name = re.sub(r',\s*$', '', name).strip()
        href = a.get('href', '')
        if name and name not in seen_names and len(name) > 1:
            seen_names.add(name)
            p = {'name': name}
            if href:
                href = urljoin('https://bangbros.com', href)
                p['url'] = href
            performers.append(p)

    # ── Tags ───────────────────────────────────────────────────────
    # Tags use path /videos/tags/ (NOT /category/ or /niches/)
    tags = []
    tag_links = tree.xpath('//a[contains(@href, "/videos/tags/")]')
    for a in tag_links:
        t = a.text_content().strip()
        if t and t not in tags:
            tags.append(t)

    # ── Studio ─────────────────────────────────────────────────────
    # The scene's subsite is in the "Information" section with a link like
    # /videos/site/115261/ass-parade/ (NOT /websites/ which is from Similar Videos)
    studio = None
    site_links = tree.xpath('//a[contains(@href, "/videos/site/")]')
    if site_links:
        studio = site_links[0].text_content().strip()
    # Fallback: look for /websites/ but only in the Information section
    if not studio:
        info_h2 = tree.xpath('//h2[contains(text(), "Information")]')
        if info_h2:
            container = info_h2[0].getparent()
            if container is not None:
                wlinks = container.xpath('.//a[contains(@href, "/websites/")]')
                if wlinks:
                    studio = wlinks[0].text_content().strip()

    # Fallback: domain-based
    if not studio:
        domain_match = re.search(r'(?:https?://(?:www\.)?)([^.]+)\.', url)
        if domain_match:
            name = domain_match.group(1).lower()
            studio_map = {
                'bangbros': 'Bang Bros',
                'sexselector': 'Sex Selector',
                'virtualporn': 'Virtual Porn',
            }
            studio = studio_map.get(name, name.title())

    # ── Code ───────────────────────────────────────────────────────
    scene_id_match = re.search(r'/video/(\d+)', url)
    code = scene_id_match.group(1) if scene_id_match else None

    # ── Duration ───────────────────────────────────────────────────
    duration_min = None
    # Try visible text: "25 min" or "1h 25m"
    m = re.search(r'(\d+)\s*min', page_text)
    if m:
        duration_min = int(m.group(1))
    else:
        m = re.search(r'(\d+)h\s*(\d+)m', page_text)
        if m:
            duration_min = int(m.group(1)) * 60 + int(m.group(2))

    # ── Date ───────────────────────────────────────────────────────
    # Date appears in an <h2> tag in the scene header, format "September 7, 2026"
    # No JSON-LD exists on BangBros pages.
    iso_date = None

    # Look for h2 tags containing a date pattern
    all_h2 = tree.xpath('//h2')
    for h2 in all_h2:
        text = h2.text_content().strip()
        # Match "Month DD, YYYY" pattern
        m = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\d{1,2},\s+\d{4})', text)
        if m:
            iso_date = _parse_date(m.group(1))
            if iso_date:
                break

    # Fallback: regex in full page text
    if not iso_date:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', page_text)
        if m:
            iso_date = _parse_date(m.group(1))

    display_date = _format_display_date(iso_date) if iso_date else None

    return {
        'kind': 'scene',
        'title': title,
        'date': iso_date,
        'releaseDate': display_date,
        'details': details,
        'code': code,
        'studio': studio,
        'durationMin': duration_min,
        'performers': performers,
        'tags': tags,
        'image': thumbnail,
        'thumbnail': thumbnail,
        'cardThumbnail': thumbnail,
        'cover_a': thumbnail,
        'cover_b': thumbnail,
        'sourceUrl': url,
        'sourceSite': 'bangbros',
    }


def scrape_performer(url):
    """Scrape a performer / model page (og:* meta tags — same pattern as the
    scene page, since these are all server-rendered Aylo-network templates)."""
    url = urljoin('https://bangbros.com', url)
    resp = _fetch(url)
    tree = lxml_html.fromstring(resp.text)

    name = None
    og_title = tree.xpath('//meta[@property="og:title"]/@content')
    if og_title:
        name = re.sub(r'\s*[-|]\s*Bang.*$', '', og_title[0].strip(), flags=re.I).strip()
    if not name:
        h1 = tree.xpath('//h1/text()')
        if h1:
            name = h1[0].strip()
    if not name:
        return {'notFound': True, 'url': url}

    details = None
    og_desc = tree.xpath('//meta[@property="og:description"]/@content')
    if og_desc:
        details = og_desc[0].strip()

    image = None
    og_image = tree.xpath('//meta[@property="og:image"]/@content')
    if og_image:
        image = og_image[0]

    return {
        'kind': 'performer',
        'name': name,
        'details': details,
        'photo': image,
        'image': image,
        'thumbnail': image,
        'cardThumbnail': image,
        'cover_a': image,
        'cover_b': image,
        'sourceUrl': url,
        'sourceSite': 'bangbros',
        'notFound': False,
    }


def search_performers(query):
    """Search BangBros for performer/model pages."""
    url = f'https://bangbros.com/search/{quote(query)}'
    resp = _fetch(url)
    tree = lxml_html.fromstring(resp.text)

    results = []
    seen = set()
    for a in tree.xpath('//a[contains(@href, "/model/")]'):
        href = a.get('href', '')
        if not href or href in seen:
            continue
        seen.add(href)
        href = urljoin('https://bangbros.com', href)
        name = a.get('title', '').strip() or a.text_content().strip()
        if name and len(name) > 1:
            results.append({'kind': 'performer', 'name': name, 'url': href})
    return results


def scrape(title="", url="", html="", kind=""):
    """Unified entry point called by the backend."""
    if url:
        if '/model/' in url:
            return scrape_performer(url)
        return scrape_scene(url)
    if title:
        if kind == 'performer':
            try:
                hits = search_performers(title)
                if hits:
                    return scrape_performer(hits[0]['url'])
            except Exception:
                pass
            return {'notFound': True}
        try:
            results = search_scenes(title)
        except Exception:
            return {'notFound': True, 'error': f'Search failed for: {title}'}
        if isinstance(results, list) and results:
            # Clean up internal field from all results
            for r in results:
                r.pop('_match_score', None)
            # Try up to 5 results (some may be dead links)
            for candidate in results[:5]:
                scene_url = candidate.get('url')
                if not scene_url:
                    continue
                try:
                    full = scrape_scene(scene_url)
                    if isinstance(full, dict) and not full.get('notFound'):
                        # Skip dead links ("Page Not Found" title)
                        t = (full.get('title') or '').lower()
                        if 'page not found' in t or 'not found' in t:
                            continue
                        for k, v in candidate.items():
                            if k not in full or full[k] is None:
                                full[k] = v
                        return full
                except Exception:
                    continue
            # All URLs failed — return first card data as fallback
            return results[0]
        if isinstance(results, dict):
            return results
        return {'notFound': True}
    return {'error': 'need url or title'}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python bangbros_scraper.py <search|scene-url> <query_or_url>')
        sys.exit(1)

    op = sys.argv[1]
    arg = sys.argv[2]

    try:
        if op == 'search':
            result = search_scenes(arg)
        elif op == 'scene-url':
            result = scrape_scene(arg)
        else:
            result = {'error': f'Unknown operation: {op}'}
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
