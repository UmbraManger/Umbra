"""
Jules Jordan network scraper (Python)
Supports: julesjordan.com, girlgirl.com, manuelferrara.com, spermswallowers.com, theassfactory.com

Fixed:
- search_scenes(): looks for <a> links with /trial/scenes/ hrefs, extracts title from <h2> child
- Scene detail: updated selectors for current layout (h1 title, /trial/models/ performers, "Released:" date)
- Removed dependency on jj-card-thumb class which may not exist
"""
import re
import json
from urllib.parse import urlparse, urljoin
from lxml import html as lxml_html
import requests


STUDIO_MAP = {
    "julesjordan": "Jules Jordan",
    "girlgirl": "Girl Girl",
    "manuelferrara": "Manuel Ferrara",
    "theassfactory": "The Ass Factory",
    "spermswallowers": "Sperm Swallowers",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _detect_site(url: str) -> str:
    host = (urlparse(url).hostname or "").replace("www.", "").split(".")[0]
    return host


def _studio_from_url(url: str) -> str:
    site = _detect_site(url)
    return STUDIO_MAP.get(site, site.title())


def _parse_date(text: str) -> str:
    """Parse various date formats to YYYY-MM-DD."""
    text = text.strip()
    # MM/DD/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    # YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return text[:10]
    # January 2, 2006
    m = re.match(r"(\w+) (\d{1,2}), (\d{4})", text)
    if m:
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
        }
        month = months.get(m.group(1).lower(), 1)
        return f"{m.group(3)}-{str(month).zfill(2)}-{m.group(2).zfill(2)}"
    return ""


def _feet_to_cm(text: str) -> int:
    """Convert 5'7" to cm."""
    m = re.match(r"(\d+)\s*['\u2032]\s*(\d+)", text)
    if m:
        total_inches = int(m.group(1)) * 12 + int(m.group(2))
        return round(total_inches * 2.54)
    m = re.match(r"(\d+)\s*\"", text)
    if m:
        return round(int(m.group(1)) * 2.54)
    return 0


def search_scenes(title: str, base_url: str = "https://www.julesjordan.com/") -> list:
    """Search for scenes by scanning trial updates listing pages.

    The listing page has <a> links pointing to /trial/scenes/Scene-Name_vids.html
    with an <h2> child containing the scene title and "Starring:" / "Released:" text.
    """
    site = _detect_site(base_url)
    listing_base = f"https://www.{site}.com/trial/updates/page_{{}}.html"
    query_norm = title.strip().lower()
    if not query_norm:
        return []

    results = []
    for page_num in range(1, 6):  # Check first 5 pages
        try:
            page_url = listing_base.format(page_num)
            r = requests.get(page_url, timeout=15, headers=HEADERS)
            if r.status_code != 200:
                break
            page_doc = lxml_html.fromstring(r.text)

            # The listing page structure is:
            #   <div class="jj-content-card">
            #     <div class="jj-card-body">
            #       <h2>Scene Title</h2>
            #       Starring: <a href="/trial/models/...">Performer</a>
            #       Released: Month DD, YYYY
            #     </div>
            #     <a href="/trial/scenes/..._vids.html">Watch Trailer</a>
            #   </div>
            # Find all jj-content-card divs that contain both an h2 and a scene link
            cards = page_doc.xpath('//div[contains(@class, "jj-content-card")]')
            if not cards:
                break

            for card in cards:
                # Get title from h2
                h2 = card.xpath('.//h2')
                if not h2:
                    continue
                card_title = h2[0].text_content().strip()
                if not card_title or len(card_title) < 3:
                    continue

                # Get scene URL from the /trial/scenes/ link in this card
                scene_link = card.xpath('.//a[contains(@href, "/trial/scenes/")]')
                if not scene_link:
                    continue
                href = (scene_link[0].get("href") or "").strip()
                if not href:
                    continue

                # Get cardThumbnail from data-thumbs attribute on jj-card-thumb link
                card_thumb = ""
                thumb_link = card.xpath('.//a[contains(@class, "jj-card-thumb")]')
                if thumb_link:
                    data_thumbs = thumb_link[0].get("data-thumbs", "")
                    if data_thumbs:
                        try:
                            thumbs = json.loads(data_thumbs)
                            if isinstance(thumbs, list) and thumbs:
                                card_thumb = thumbs[0]
                        except json.JSONDecodeError:
                            pass
                if not card_thumb:
                    # "What's Hot" featured card: plain <div class="jj-card-thumb"><img src="...">
                    img_src = card.xpath('.//div[contains(@class,"jj-card-thumb")]//img/@src')
                    if img_src:
                        card_thumb = urljoin(page_url, img_src[0])

                if query_norm in card_title.lower():
                    full_url = urljoin(page_url, href)
                    entry = {
                        "title": card_title,
                        "url": full_url,
                    }
                    if card_thumb:
                        entry["cardThumbnail"] = card_thumb
                    results.append(entry)

        except Exception:
            break
        if results:
            break

    # The same scene can legitimately appear twice on a listing page (e.g. once
    # in a "What's Hot" style featured card, once in the regular grid) — if so,
    # dedupe by URL and keep whichever copy actually carries a cardThumbnail.
    by_url = {}
    for entry in results:
        existing = by_url.get(entry["url"])
        if existing is None or ("cardThumbnail" not in existing and "cardThumbnail" in entry):
            by_url[entry["url"]] = entry
    return list(by_url.values())


def _find_card_thumbnail(base_url: str, scene_url: str) -> str:
    """Scan the trial updates listing pages to find the cardThumbnail for a
    specific scene, matched by URL slug.

    Reuses the same jj-content-card / data-thumbs structure search_scenes()
    already scans — used here as a last-resort fallback when og:image and
    JSON-LD thumbnailUrl don't yield a cardThumbnail (e.g. when scraping
    directly from a pasted URL rather than arriving via search).

    Note: listing cards link to /trial/scenes/..._vids.html — if scene_url is
    the other URL format (/trial/movies/<id>/<slug>.html), the slugs won't
    match and this will come back empty. It's a best-effort fallback, not
    guaranteed to find anything.
    """
    site = _detect_site(base_url)
    listing_base = f"https://www.{site}.com/trial/updates/page_{{}}.html"
    target_slug = scene_url.rstrip("/").split("/")[-1] if scene_url else ""
    if not target_slug:
        return ""

    for page_num in range(1, 6):  # same 5-page cap as search_scenes
        try:
            page_url = listing_base.format(page_num)
            r = requests.get(page_url, timeout=15, headers=HEADERS)
            if r.status_code != 200:
                break
            page_doc = lxml_html.fromstring(r.text)
            cards = page_doc.xpath('//div[contains(@class, "jj-content-card")]')
            if not cards:
                break

            for card in cards:
                scene_link = card.xpath('.//a[contains(@href, "/trial/scenes/")]')
                if not scene_link:
                    continue
                href = (scene_link[0].get("href") or "").strip()
                if not href or href.rstrip("/").split("/")[-1] != target_slug:
                    continue

                # Regular grid card: <a class="jj-card-thumb" data-thumbs="[...]">
                thumb_link = card.xpath('.//a[contains(@class, "jj-card-thumb")]')
                if thumb_link:
                    data_thumbs = thumb_link[0].get("data-thumbs", "")
                    if data_thumbs:
                        try:
                            thumbs = json.loads(data_thumbs)
                            if isinstance(thumbs, list) and thumbs:
                                return urljoin(page_url, thumbs[0])
                        except json.JSONDecodeError:
                            pass

                # "What's Hot" featured card: plain <div class="jj-card-thumb"><img src="...">
                img_src = card.xpath('.//div[contains(@class,"jj-card-thumb")]//img/@src')
                if img_src:
                    return urljoin(page_url, img_src[0])

                # This card matched by URL but had no usable thumbnail at all —
                # keep scanning rather than giving up, in case the same scene
                # appears again elsewhere on the page (e.g. once in "What's Hot",
                # once in the regular grid) with a card that does have one.
        except Exception:
            break

    return ""


# ── Movie ("groups") extraction ───────────────────────────────────
# Scene pages link to /dvds/ and /movies/ in two very different ways:
#   * navigation ("Movies", "DVDs") → the listing index, never a title
#   * this scene's movie            → a specific /dvds/<id>/<slug>.html page
# Only the second kind belongs in a scene's movie field.
_GENERIC_GROUP_LABELS = {
    "movie", "movies", "dvd", "dvds", "film", "films", "series",
    "scenes", "scene", "categories", "category", "pornstars", "models",
    "home", "trailers", "latest", "new releases", "more", "search",
    "login", "join", "subscribe", "watch", "all",
}
_INDEX_SLUGS = {"", "index.html", "index.htm", "index.php", "list.php", "all.php"}
_CHROME_HINT = re.compile(r"(\bmenu\b|navbar|navigation|\bnav\b|\bfooter\b|\bbanner\b|\bpromo\b)", re.I)
_BOX_HINT = re.compile(r"(sidebar|side-bar|\brelated\b|recommend|more[-_ ]?scenes)", re.I)
_MOVIE_LABEL = re.compile(r"^(?:movies?|dvds?|films?|series)\s*[:\-]?\s*(.+)$", re.I)
_MOVIE_WORD = re.compile(r"\b(movie|movies|dvd|dvds|series|film)\b", re.I)


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def _hint_of(el) -> str:
    return " ".join(str(el.get(k) or "") for k in ("class", "id"))


def _in_chrome(el) -> bool:
    """True when the element sits in page chrome (nav/header/footer/menu/banner)."""
    for anc in el.iterancestors():
        if getattr(anc, "tag", None) in ("nav", "header", "footer"):
            return True
        hint = _hint_of(anc)
        if hint and _CHROME_HINT.search(hint):
            return True
    return False


def _in_side_box(el) -> bool:
    """True for secondary blocks (sidebar, related/recommended rows)."""
    for anc in el.iterancestors():
        hint = _hint_of(anc)
        if hint and _BOX_HINT.search(hint):
            return True
    return False


def _movie_groups(doc, base_url: str, meta_items=None) -> list:
    """Movie links found on a scene page, best candidate first.

    A labelled detail row ("MovieSome Title") wins, then links the page
    actually presents as this scene's movie, then any other specific
    movie link. Nav links to the movie listing are dropped so the scene
    never ends up filed under a title like "Movies".
    """
    labelled = ""
    for mi in (meta_items or []):
        text = _norm(mi.text_content())
        if len(text) > 120:
            continue
        m = _MOVIE_LABEL.match(text)
        if not m:
            continue
        value = m.group(1).strip()
        if len(value) >= 2 and value.lower().rstrip(":/ ") not in _GENERIC_GROUP_LABELS:
            labelled = value
            break

    candidates = []
    links = doc.xpath('//a[contains(@href, "/dvds/") or contains(@href, "/movies/")]')
    for i, a in enumerate(links):
        name = _norm(a.text_content())
        if not name:
            continue
        if name.lower().rstrip(":/ ") in _GENERIC_GROUP_LABELS:
            continue
        if _in_chrome(a):
            continue
        segs = [s for s in urlparse(a.get("href") or "").path.split("/") if s]
        try:
            k = next(n for n, s in enumerate(segs) if s.lower() in ("dvds", "movies"))
        except StopIteration:
            continue
        if not [s for s in segs[k + 1:] if s.lower() not in _INDEX_SLUGS]:
            continue          # points at the listing itself, not at a movie
        tier = 1
        parent = a.getparent()
        ctx = _norm(parent.text_content()) if parent is not None else ""
        near_label = bool(labelled and name.lower() == labelled.lower()) or bool(
            ctx and len(ctx) <= 160 and _MOVIE_WORD.search(ctx))
        if _in_side_box(a):
            tier = 1 if near_label else 2
        elif near_label:
            tier = 0
        candidates.append((tier, i, name, a.get("href") or ""))

    candidates.sort(key=lambda c: (c[0], c[1]))
    groups = []
    seen = set()
    if labelled:
        entry = {"name": labelled}
        for _, _, name, href in candidates:
            if name.lower() == labelled.lower() and href:
                entry["url"] = urljoin(base_url, href)
                break
        groups.append(entry)
        seen.add(labelled.lower())
    for _, _, name, href in candidates:
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        g = {"name": name}
        if href:
            g["url"] = urljoin(base_url, href)
        groups.append(g)
    return groups


def scrape_scene_detail(url: str, html: str = "") -> dict:
    """Scrape a JulesJordan scene detail page.

    Current layout (julesjordan.com/trial/scenes/...):
    - Title in <h1>
    - Performers as links to /trial/models/...
    - Date in "Released: Month DD, YYYY"
    - Description in a paragraph after the title
    - Categories as links to category.php
    - Image: video poster or og:image
    """
    if not html:
        r = requests.get(url, timeout=25, headers=HEADERS)
        r.raise_for_status()
        html = r.text

    doc = lxml_html.fromstring(html)
    base_url = url
    site = _detect_site(base_url)
    out = {"kind": "scene", "studio": _studio_from_url(base_url)}

    # ── Title ──────────────────────────────────────────────────────
    # Try <h1> first (current layout)
    h1 = doc.xpath('//h1')
    if h1:
        out["title"] = h1[0].text_content().strip()
    else:
        # Fallback: scene-title class (26Redesign)
        scene_title = doc.xpath('//h1[@class="scene-title"]/text()')
        if scene_title:
            out["title"] = scene_title[0].strip()
        else:
            # Fallback: og:title
            og_title = doc.xpath('//meta[@property="og:title"]/@content')
            if og_title:
                out["title"] = og_title[0].strip()

    # ── Date ───────────────────────────────────────────────────────
    # Date is in a div.meta-item with "Released" label
    # Structure: <div class="meta-item">Released<div>September 7, 2026</div></div>
    meta_items = doc.xpath('//div[contains(@class, "meta-item")]')
    for mi in meta_items:
        mi_text = mi.text_content().strip()
        if 'Released' in mi_text:
            m = re.search(r'([A-Z][a-z]+\s+\d{1,2},\s+\d{4})', mi_text)
            if m:
                out["date"] = _parse_date(m.group(1))
                break

    # Fallback: JSON-LD uploadDate
    if "date" not in out:
        ld_scripts = doc.xpath('//script[@type="application/ld+json"]/text()')
        for script in ld_scripts:
            m = re.search(r'"uploadDate"\s*:\s*"(\d{4}-\d{2}-\d{2})', script)
            if m:
                out["date"] = m.group(1)
                break

    # ── Description ────────────────────────────────────────────────
    # Look for a paragraph near the title
    desc = doc.xpath('//div[@class="scene-desc"]/text()')
    if desc:
        out["details"] = " ".join(d.strip() for d in desc if d.strip())
    else:
        # Try meta description
        og_desc = doc.xpath('//meta[@property="og:description"]/@content')
        if og_desc:
            out["details"] = og_desc[0].strip()

    # ── Performers ─────────────────────────────────────────────────
    # Performers are in the first div.meta-item containing "Starring"
    # Structure: <div class="meta-item">Starring<div>Angela White, Emma Rosie, Zac Wild</div></div>
    performers = []
    seen_names = set()
    for mi in meta_items:
        mi_text = mi.text_content().strip()
        if mi_text.startswith('Starring'):
            # Get performer links from this meta-item only
            perf_links = mi.xpath('.//a[contains(@href, "/trial/models/")]')
            for a in perf_links:
                name = a.text_content().strip()
                href = a.get("href", "")
                if name and name not in seen_names and len(name) > 1:
                    seen_names.add(name)
                    p = {"name": name}
                    if href:
                        p["url"] = urljoin(base_url, href)
                    performers.append(p)
            break  # Only use the first Starring section

    # Fallback: if no performers found in meta-item, try all /trial/models/ links
    # but exclude nav links and "More Scenes" section
    if not performers:
        perf_links = doc.xpath('//a[contains(@href, "/trial/models/")]')
        for a in perf_links:
            name = a.text_content().strip()
            href = a.get("href", "")
            # Skip nav links like "Pornstars" and links in jj-card-body (More Scenes)
            parent_class = (a.getparent().get('class', '') or '') if a.getparent() is not None else ''
            if 'jj-card' in parent_class:
                continue
            if name.lower() in ('pornstars', 'models', 'scenes'):
                continue
            if name and name not in seen_names and len(name) > 1:
                seen_names.add(name)
                p = {"name": name}
                if href:
                    p["url"] = urljoin(base_url, href)
                performers.append(p)
    out["performers"] = performers

    # ── Tags / Categories ──────────────────────────────────────────
    tags = []
    # Links to category.php or categories (skip nav links)
    _NAV_TAGS = {'scenes', 'categories', 'movies', 'pornstars', 'home'}
    cat_links = doc.xpath(
        '//a[contains(@href, "category.php") or contains(@href, "/categories/")]'
    )
    for a in cat_links:
        t = a.text_content().strip()
        if t and t.lower() not in _NAV_TAGS and t not in tags:
            tags.append(t)
    out["tags"] = tags

    # ── Groups (Movies/DVDs) ───────────────────────────────────────
    groups = _movie_groups(doc, base_url, meta_items)
    if groups:
        out["groups"] = groups

    # ── Image ──────────────────────────────────────────────────────
    # Matching old file's image scheme:
    #   image       = main image (video poster)
    #   thumbnail   = cover player (same as image)
    #   cardThumbnail = cover thumbnail (og:image or JSON-LD)

    # 1. video#video-player[poster] → cover player (image + thumbnail)
    poster = doc.xpath('//video[@id="video-player"]/@poster') or doc.xpath('//video/@poster')
    if poster:
        out["image"] = urljoin(base_url, poster[0])
        out["thumbnail"] = urljoin(base_url, poster[0])

    # 2. Listing-page data-thumbs[0] → cardThumbnail (tried FIRST: this is the
    #    site's own designated "first" thumbnail for the scene, verified against
    #    real markup. og:image can point at a different image than what's shown
    #    as the cover on listing pages, so it's only used as a fallback now.
    #    Only matches when url is in the /trial/scenes/..._vids.html format that
    #    listing cards actually link to — otherwise this comes back empty and
    #    falls through to og:image below.
    card_thumb = _find_card_thumbnail(base_url, url)
    if card_thumb:
        out["cardThumbnail"] = card_thumb

    # Fallback: og:image
    if "cardThumbnail" not in out:
        og_image = doc.xpath('//meta[@property="og:image"]/@content')
        if og_image:
            out["cardThumbnail"] = og_image[0]

    # Fallback: JSON-LD thumbnailUrl for cardThumbnail
    if "cardThumbnail" not in out:
        for script in doc.xpath('//script[@type="application/ld+json"]/text()'):
            try:
                ld = json.loads(script)
                if ld.get("@type") == "VideoObject":
                    ld_thumb = ld.get("thumbnailUrl", "")
                    if isinstance(ld_thumb, list):
                        ld_thumb = ld_thumb[0] if ld_thumb else ""
                    if ld_thumb:
                        out["cardThumbnail"] = urljoin(base_url, ld_thumb)
                    break
            except (json.JSONDecodeError, KeyError):
                continue

    # Last resort: use poster for cardThumbnail too
    if "cardThumbnail" not in out and poster:
        out["cardThumbnail"] = urljoin(base_url, poster[0])

    return out


def scrape(title: str = "", url: str = "", html: str = "") -> dict:
    """
    Main scrape function.
    Returns dict with keys:
    - kind: "scene" | "movie" | "performer"
    - title, date, details, tags, performers, studio, groups
    - image: main image (video poster)
    - thumbnail: cover player image
    - cardThumbnail: cover thumbnail
    """
    if not html and not url and not title:
        return {"error": "need url, html, or title"}

    _search_card_thumb = ""

    if not html and not url:
        hits = search_scenes(title)
        if not hits:
            return {"notFound": True, "query": title}
        url = hits[0]["url"]
        _search_card_thumb = hits[0].get("cardThumbnail", "")

    if html:
        out = scrape_scene_detail(url, html=html)
        if _search_card_thumb and "cardThumbnail" not in out:
            out["cardThumbnail"] = _search_card_thumb
        return out

    # Fetch the page
    r = requests.get(url, timeout=25, headers=HEADERS)
    r.raise_for_status()
    html_content = r.text
    doc = lxml_html.fromstring(html_content)
    base_url = url

    # Detect page type
    # ── Performer page ─────────────────────────────────────────────
    if "/models/" in url or "/pornstar/" in url:
        out = {"kind": "performer", "studio": _studio_from_url(base_url)}

        title_bar = doc.xpath("//span[@class='title_bar_hilite']/text()")
        if title_bar:
            out["name"] = title_bar[0].strip()
        else:
            h1 = doc.xpath('//h1/text()')
            if h1:
                out["name"] = h1[0].strip()

        bio = doc.xpath("//div[@class='model_bio model_bio_info']//text()")
        bio_text = " ".join(b.strip() for b in bio if b.strip())

        m = re.search(r"Measurements:\s*([\d\w\s]+)", bio_text)
        if m:
            out["measurements"] = m.group(1).strip()

        m = re.search(r"Height:\s*([\d'\"]+)", bio_text)
        if m:
            out["height"] = _feet_to_cm(m.group(1))

        img = doc.xpath("//img[contains(@class,'model_bio_thumb')]/@src0_3x")
        if not img:
            img = doc.xpath("//img[contains(@class,'model_bio_thumb')]/@src")
        if img:
            out["image"] = urljoin(base_url, img[0])

        return out

    # ── Scene page ─────────────────────────────────────────────────
    out = scrape_scene_detail(url, html=html_content)
    # cardThumbnail from search data-thumbs takes priority over og:image
    if _search_card_thumb:
        out["cardThumbnail"] = _search_card_thumb
    return out


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Usage: python julesjordan.py <search|scene-url> <query_or_url>')
        sys.exit(1)

    op = sys.argv[1]
    arg = sys.argv[2]

    try:
        if op == 'search':
            result = search_scenes(arg)
        elif op == 'scene-url':
            result = scrape_scene_detail(arg)
        else:
            result = {'error': f'Unknown operation: {op}'}
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
