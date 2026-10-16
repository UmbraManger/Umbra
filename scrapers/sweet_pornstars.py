"""
Sweet-Pornstars.com Scraper for Umbra
========================================
Searches performers and scenes via the sweet-pornstars.com JSON API.

API Endpoints Used:
  - /api/search/models/?q=<query>          → search performers
  - /api/model/<slug>/                     → performer details
  - /api/search/scenes/?q=<query>          → search scenes
  - /api/model/<id>/scenes/?page=1         → performer's scenes
  - /api/filter/scenes/?o=-date_added      → latest scenes

Usage:
  Standalone:  python sweet_pornstars.py performer "Kylie Rocket"
               python sweet_pornstars.py scene "Kylie Rocket"
  As module:   from sweet_pornstars import search
               result = search("Kylie Rocket", kind="performer")
"""

import sys
import json
import re
import requests
from urllib.parse import quote_plus

BASE = "https://www.sweet-pornstars.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "application/json"}


def _get(path, params=None):
    """GET request to the sweet-pornstars API."""
    url = BASE + path
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _search_models(query):
    """Search for performers by name."""
    data = _get("/api/search/models/", {"q": query})
    if isinstance(data, list):
        return data
    return data.get("results", []) if isinstance(data, dict) else []


def _get_model(slug):
    """Get detailed performer info by slug."""
    return _get(f"/api/model/{slug}/")


def _get_model_scenes(model_id, page=1):
    """Get scenes for a performer by model ID."""
    return _get(f"/api/model/{model_id}/scenes/", {"page": page})


def _search_scenes(query):
    """Search for scenes by title/performer name."""
    data = _get("/api/search/scenes/", {"q": query})
    if isinstance(data, list):
        return data
    return data.get("results", []) if isinstance(data, dict) else []


def _get_scene_detail(model_slug, gallery_slug):
    """Get full scene detail including gallery images."""
    return _get(f"/api/scene/{model_slug}/{gallery_slug}/")


def _parse_date(s):
    """Extract YYYY-MM-DD from ISO datetime string."""
    if not s:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(s))
    return m.group(1) if m else None


def _strip_html(text):
    """Remove HTML tags from text."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


# ── Performer Lookup ──────────────────────────────────────────────────────────

def lookup_performer(name, **kwargs):
    """Search for a performer and return detailed info in Umbra format."""
    results = _search_models(name)
    if not results:
        return None

    # Find best match (exact or first)
    target = name.strip().lower()
    best = None
    for r in results:
        if r.get("model_name", "").strip().lower() == target:
            best = r
            break
    if not best:
        best = results[0]

    slug = best.get("slug", "")
    if not slug:
        return None

    # Fetch detailed info
    detail = _get_model(slug)
    if not detail or "detail" in detail:
        return None

    # Map to Umbra performer fields
    country = detail.get("country") or {}
    ethnicity = detail.get("ethnicity") or {}

    result = {
        "name": detail.get("model_name", name),
        "gender": "f",  # sweet-pornstars only has female performers
        "photo": _abs_url(detail.get("photo", "")),
        "nationality": country.get("country_name", ""),
        "ethnicity": ethnicity.get("ethnicity_name", ""),
        "twitter": detail.get("twitter", "") or "",
        "instagram": "",
        "onlyfans": "",
        "aliases": detail.get("model_aliases", "") or "",
        "birth": None,
        "height": None,
        "weight": None,
        "hair": "",
        "eyes": "",
        "measurements": "",
        "boobs": "",
        "piercings": "",
        "tattoos": "",
        "career_start": "",
        "urls": [],
    }

    # Add profile URL as reference
    profile_url = f"{BASE}/pornstars/{slug}/"
    result["urls"] = [profile_url]

    return result


# ── Scene Lookup ──────────────────────────────────────────────────────────────

def lookup_scenes_by_performer(name, max_pages=3, **kwargs):
    """Search for scenes featuring a performer."""
    results = _search_models(name)
    if not results:
        return []

    target = name.strip().lower()
    best = None
    for r in results:
        if r.get("model_name", "").strip().lower() == target:
            best = r
            break
    if not best:
        best = results[0]

    model_id = best.get("id")
    if not model_id:
        return []

    scenes = []
    page = 1
    while page <= max_pages:
        data = _get_model_scenes(model_id, page=page)
        results_list = data.get("results", [])
        if not results_list:
            break

        for sc in results_list:
            scene = _parse_scene(sc)
            if scene:
                scenes.append(scene)

        if not data.get("next"):
            break
        page += 1

    return scenes


def search_scenes(query, max_pages=2, **kwargs):
    """Search for scenes by title or keyword."""
    results = _search_scenes(query)
    if not results:
        return []

    scenes = []
    for sc in results[:50]:  # Limit to 50 results
        scene = _parse_scene(sc)
        if scene:
            scenes.append(scene)

    return scenes


def _parse_scene(sc):
    """Parse a scene API response into Umbra format."""
    title = sc.get("pagetitle", "")
    if not title:
        return None

    site = sc.get("site") or {}
    studio_name = site.get("site_name", "")
    poster = sc.get("poster") or {}

    # Get cover image
    cover = poster.get("image", "")
    if cover and not cover.startswith("http"):
        cover = BASE + cover

    # Get thumbnail
    thumb = poster.get("thumb", "")
    if thumb and not thumb.startswith("http"):
        thumb = BASE + thumb

    # Get performers in scene
    pornstars = sc.get("pornstars") or []

    # Parse date
    date = _parse_date(sc.get("date_added"))

    return {
        "title": title,
        "date": date,
        "studio": studio_name,
        "covers": [cover] if cover else [],
        "thumb": 0,
        "duration_min": None,
        "director": "",
        "desc": "",
        "categories": [],
        "actors": [p.get("model_name", "") for p in pornstars if p.get("model_name")],
        "source_url": f"{BASE}/scenes/{sc.get('slug', '')}/",
        "_model_slug": sc.get("slug_parent", ""),
        "_gallery_slug": sc.get("slug", ""),
    }


def fetch_gallery(model_slug, gallery_slug, count=12, **kwargs):
    """Fetch gallery images for a scene. Returns list of absolute image URLs.

    Args:
        model_slug: Performer slug (e.g. 'juniper-ren')
        gallery_slug: Scene slug (e.g. 'juniper-ren-passion-hd-the-crush')
        count: Number of gallery images to return (default 12)
    """
    if not model_slug or not gallery_slug:
        return []
    try:
        detail = _get_scene_detail(model_slug, gallery_slug)
    except Exception:
        return []
    images = detail.get("images") or []
    # Sort by rank and take requested count
    images.sort(key=lambda x: x.get("rank", 0))
    result = []
    for img in images[:count]:
        url = img.get("image", "")
        if url and not url.startswith("http"):
            url = BASE + url
        if url:
            result.append(url)
    return result


def _abs_url(url):
    """Make a URL absolute if it's relative."""
    if not url:
        return ""
    if url.startswith("http"):
        return url
    return BASE + url


# ── Combined Search ───────────────────────────────────────────────────────────

def search(query, kind="performer", **kwargs):
    """Main search function. Returns data in Umbra scraper format."""
    gallery_count = int(
        kwargs.get("gallery_count")
        or kwargs.get("gallery count")
        or kwargs.get("galleryCount")
        or 12
    )
    if kind == "performer":
        result = lookup_performer(query)
        return result or {}
    elif kind == "scene":
        scenes = search_scenes(query)
        if not scenes:
            scenes = lookup_scenes_by_performer(query)
        if scenes:
            scene = scenes[0]
            # Fetch gallery if requested
            if gallery_count > 0:
                try:
                    ms = scene.get("_model_slug", "")
                    gs = scene.get("_gallery_slug", "")
                    scene["gallery"] = fetch_gallery(ms, gs, gallery_count)
                except Exception:
                    scene["gallery"] = []
            # Clean internal slugs from output
            scene.pop("_model_slug", None)
            scene.pop("_gallery_slug", None)
            return scene
        return {}
    elif kind == "movie":
        # Treat "movie" as a scene collection for this site
        scenes = lookup_scenes_by_performer(query, max_pages=5)
        if not scenes:
            scenes = search_scenes(query, max_pages=3)
        if scenes:
            return {
                "title": query,
                "scenes": len(scenes),
                "desc": f"Collection of {len(scenes)} scenes from sweet-pornstars.com",
            }
        return {}
    return {}


# Alias for backends that call run() instead of search()
run = search

# Alias for backends that call scrape(title=, url=, html=, ...)
def scrape(title=None, url=None, html=None, query=None, kind="scene", **kwargs):
    gallery_count = int(kwargs.get("gallery_count") or kwargs.get("gallery count") or 12)

    # If URL provided, parse slugs and fetch gallery directly
    if url and "sweet-pornstars.com" in url:
        parts = url.rstrip("/").split("/")
        # URL format: .../model-slug/gallery-slug
        if len(parts) >= 2:
            model_slug = parts[-2]
            gallery_slug = parts[-1]
            gallery = fetch_gallery(model_slug, gallery_slug, gallery_count)
            if gallery:
                # Also try to get scene info from the API
                try:
                    detail = _get_scene_detail(model_slug, gallery_slug)
                    title = detail.get("pagetitle") or detail.get("title") or title or ""
                    site = detail.get("site") or {}
                    studio = site.get("site_name", "")
                    pornstars = detail.get("pornstars") or []
                    date = _parse_date(detail.get("date_added"))
                    poster = detail.get("poster") or {}
                    cover = poster.get("image", "")
                    if cover and not cover.startswith("http"):
                        cover = BASE + cover
                    return {
                        "title": title,
                        "date": date,
                        "studio": studio,
                        "covers": [cover] if cover else [],
                        "gallery": gallery,
                        "actors": [p.get("model_name", "") for p in pornstars if p.get("model_name")],
                        "source_url": url,
                    }
                except Exception:
                    return {"gallery": gallery, "source_url": url}
    # Fallback to search by title
    q = title or query or ""
    return search(q, kind=kind, **kwargs)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_result(data):
    """Pretty-print result as JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python sweet_pornstars.py <performer|scene|movie> <name> [--gallery N]")
        print()
        print("Examples:")
        print("  python sweet_pornstars.py performer 'Kylie Rocket'")
        print("  python sweet_pornstars.py scene 'Kylie Rocket'")
        print("  python sweet_pornstars.py scene 'Kylie Rocket' --gallery 12")
        sys.exit(1)

    args = sys.argv[1:]
    gallery_count = 0
    if "--gallery" in args:
        gi = args.index("--gallery")
        if gi + 1 < len(args):
            try:
                gallery_count = int(args[gi + 1])
            except ValueError:
                pass
        args = args[:gi] + args[gi + 2:]

    kind = args[0].lower()
    query = " ".join(args[1:])

    print(f"Searching sweet-pornstars.com for {kind}: {query!r} ...", file=sys.stderr)

    if kind == "performer":
        result = lookup_performer(query)
        if result:
            _print_result(result)
        else:
            print("No performer found.", file=sys.stderr)
            sys.exit(1)

    elif kind == "scene":
        scenes = search_scenes(query)
        if not scenes:
            scenes = lookup_scenes_by_performer(query)
        if scenes:
            print(f"Found {len(scenes)} scenes:", file=sys.stderr)
            if gallery_count > 0:
                for sc in scenes:
                    ms = sc.get("_model_slug", "")
                    gs = sc.get("_gallery_slug", "")
                    sc["gallery"] = fetch_gallery(ms, gs, gallery_count)
                    sc.pop("_model_slug", None)
                    sc.pop("_gallery_slug", None)
            _print_result(scenes)
        else:
            print("No scenes found.", file=sys.stderr)
            sys.exit(1)

    elif kind == "movie":
        scenes = lookup_scenes_by_performer(query, max_pages=5)
        if not scenes:
            scenes = search_scenes(query, max_pages=3)
        if scenes:
            for sc in scenes:
                sc.pop("_model_slug", None)
                sc.pop("_gallery_slug", None)
            print(f"Found {len(scenes)} scenes for collection:", file=sys.stderr)
            _print_result({
                "title": query,
                "scenes_count": len(scenes),
                "scenes": scenes,
            })
        else:
            print("No scenes found.", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown kind: {kind!r}. Use 'performer', 'scene', or 'movie'.", file=sys.stderr)
        sys.exit(1)
