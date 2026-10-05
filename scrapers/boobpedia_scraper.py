#!/usr/bin/env python3
"""Boobpedia scraper — adapted from stashapp/CommunityScrapers (scrapers/Boobpedia.yml).
Usage:
  python3 boobpedia_scraper.py search "Name"
  python3 boobpedia_scraper.py url "https://www.boobpedia.com/boobs/Name"
"""

import json
import re
import sys
from datetime import datetime
from urllib.parse import urljoin

import cloudscraper
from lxml import html as lxml_html

BASE = "https://www.boobpedia.com"

# Use cloudscraper to bypass Cloudflare
session = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
try:
    _warmup = session.get(f'{BASE}/', timeout=(5, 10))
    print(f"[boobpedia] Warm-up status: {_warmup.status_code}", file=sys.stderr)
except Exception as _e:
    print(f"[boobpedia] Warm-up failed: {_e}", file=sys.stderr)


def strip_refs(s):
    """Remove wiki reference markers like [1], [2] etc."""
    if s is None:
        return s
    return re.sub(r'\[\d*\]', '', s).strip()


def field_after_bold(tree, label, contains=False):
    """Find <td> that follows a <b>label</b> in the same row, mirroring the
    //table//tr/td/b[text()='X']/../following-sibling::td xpath pattern used
    by the Boobpedia.yml scraper."""
    if contains:
        xp = f'//table//tr/td/b[contains(text(), "{label}")]/../following-sibling::td[1]'
    else:
        xp = f'//table//tr/td/b[text()="{label}"]/../following-sibling::td[1]'
    els = tree.xpath(xp)
    return els[0] if els else None


def sanitize_boobs(s):
    if not s:
        return s
    low = s.lower()
    if "enhanced" in low or "fake" in low or "implant" in low:
        return "Enhanced"
    if "natural" in low:
        return "Natural"
    return s


def sanitize_hair_color(s):
    if not s:
        return s
    if s.strip().lower() == "brown":
        return "Brunette"
    return s


def parse_birthdate(raw):
    """raw looks like 'January 2 1990' (day without leading zero, no comma)
    once trimmed down to the year, matching the Boobpedia.yml postProcess."""
    if not raw:
        return None
    m = re.search(r'(.*\d{4})', raw)
    cleaned = m.group(1).strip() if m else raw.strip()
    for fmt in ("%B %d %Y", "%B %d, %Y", "%d %B %Y"):
        try:
            d = datetime.strptime(cleaned, fmt)
            return d.strftime("%B %d, %Y")
        except ValueError:
            continue
    return cleaned


def performer_from_url(url):
    scraped = session.get(url, timeout=(5, 15))
    scraped.raise_for_status()
    tree = lxml_html.fromstring(scraped.text)

    # Name (MediaWiki page heading)
    h1 = tree.xpath('//h1[1]//text()')
    if not h1:
        return {"notFound": True, "url": url}
    name = "".join(h1).strip()
    if not name:
        return {"notFound": True, "url": url}

    performer = {"name": name, "boobpediaUrl": url}

    # Twitter / X / Instagram / OnlyFans — try multiple label patterns
    social_els = tree.xpath("//table//tr/td/a[contains(@href,'twitter.com') or contains(@href,'x.com') or contains(@href,'instagram.com') or contains(@href,'onlyfans.com')]/@href")
    if not social_els:
        # Fallback: look for bold labels "Twitter", "X", "Instagram", "OnlyFans"
        for label in ("Twitter", "X", "Instagram", "OnlyFans"):
            found = tree.xpath(f"//table//tr/td/a[b[text()='{label}']]/@href")
            social_els.extend(found)
    onlyfans_links = []
    for href in social_els:
        low = href.lower()
        if 'twitter.com' in low or ('x.com' in low and 'onlyfans' not in low):
            handle = href.rstrip('/').split('/')[-1]
            if handle and handle not in ('twitter', 'x', 'com', 'intent', 'status'):
                performer['twitter'] = '@' + handle
        elif 'instagram.com' in low:
            handle = href.rstrip('/').split('/')[-1]
            if handle and handle not in ('instagram', 'com', 'accounts', 'p', 'explore'):
                performer['instagram'] = '@' + handle
        elif 'onlyfans.com' in low:
            handle = href.rstrip('/').split('/')[-1]
            if handle and handle not in ('onlyfans', 'com'):
                onlyfans_links.append(handle)
    # Prefer paid OnlyFans (no 'free' in username) over free
    if onlyfans_links:
        paid = [h for h in onlyfans_links if 'free' not in h.lower()]
        performer['onlyfans'] = paid[0] if paid else onlyfans_links[0]

    # Birthdate
    born_td = field_after_bold(tree, "Born")
    if born_td is not None:
        links = born_td.xpath('.//a')
        if links:
            raw = " ".join(a.text_content().strip() for a in links)
        else:
            raw = born_td.text_content().strip()
        parsed = parse_birthdate(raw)
        if parsed:
            performer["birthday"] = parsed

    # Ethnicity
    eth_td = field_after_bold(tree, "Ethnicity")
    if eth_td is not None:
        a = eth_td.xpath('.//a')
        ethnicity = strip_refs(a[0].text_content()) if a else strip_refs(eth_td.text_content())
        if ethnicity:
            performer["ethnicity"] = ethnicity.upper()

    # Nationality (demonym, as shown on the page — no country-name remap)
    nat_td = field_after_bold(tree, "Nationality")
    if nat_td is not None:
        a = nat_td.xpath('.//a')
        nationality = strip_refs(a[0].text_content()) if a else strip_refs(nat_td.text_content())
        if nationality:
            performer["nationality"] = nationality

    # Eye color
    eye_td = field_after_bold(tree, "Eye color")
    if eye_td is not None:
        eye = strip_refs(eye_td.text_content())
        if eye:
            performer["eyeColor"] = eye

    # Hair color (label sometimes just "Hair")
    hair_td = field_after_bold(tree, "Hair", contains=True)
    if hair_td is not None:
        hair = strip_refs(hair_td.text_content().replace("\xa0", " "))
        hair = re.sub(r'\s+', ' ', hair).strip(" ,")
        if hair:
            performer["hairColor"] = sanitize_hair_color(hair)

    # Height -> cm
    height_td = field_after_bold(tree, "Height")
    if height_td is not None:
        txt = height_td.text_content()
        m = re.search(r'(\d+\.\d+)\s*m', txt)
        if m:
            performer["height"] = int(round(float(m.group(1)) * 100))

    # Weight -> kg
    weight_td = field_after_bold(tree, "Weight")
    if weight_td is not None:
        txt = weight_td.text_content()
        m = re.search(r'(\d+)\s*kg', txt)
        if m:
            performer["weight"] = int(m.group(1))

    # Measurements (combine band/waist/hip with cup size, like Babepedia scraper does)
    meas_td = field_after_bold(tree, "Measurements")
    cup_td = None
    if meas_td is None:
        # //table//tr/td[contains(b,'cup')]/following-sibling::td
        cup_rows = tree.xpath("//table//tr/td[contains(b,'cup')]/following-sibling::td[1]")
        cup_td = cup_rows[0] if cup_rows else None
        meas_td = cup_td
    if meas_td is not None:
        raw = strip_refs(meas_td.text_content()).replace(" in", "")
        m = re.search(r'(\d+)\D+(\d+)\D+(\d+)', raw)
        cup_m = re.search(r'(\d+\S{1,3})\s*cup', raw, re.IGNORECASE) or re.search(r'\((\d+\S+)\)', raw)
        if m and cup_m:
            _, waist, hip = m.groups()
            performer["measurements"] = f"{cup_m.group(1)}-{waist}-{hip}"
        elif m:
            performer["measurements"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # Boobs (FakeTits)
    boobs_td = field_after_bold(tree, "Boobs")
    if boobs_td is not None:
        a = boobs_td.xpath('.//a')
        raw_boobs = strip_refs(a[0].text_content()) if a else strip_refs(boobs_td.text_content())
        if raw_boobs:
            performer["boobs"] = sanitize_boobs(raw_boobs)

    # Career length / active years
    active_td = field_after_bold(tree, "active", contains=True)
    if active_td is not None:
        raw = strip_refs(active_td.text_content())
        raw = re.sub(r'(—|–)', '-', raw)
        raw = re.sub(r'(?i)(present|current)', '', raw).strip(" -")
        if raw:
            performer["activeYears"] = raw

    # Aliases ("also known as")
    aka_td = field_after_bold(tree, "known", contains=True)
    if aka_td is not None:
        raw = strip_refs(aka_td.text_content())
        if raw:
            performer["aliases"] = raw

    # Bio / details
    paragraphs = tree.xpath('//div[@class="mw-parser-output"]/p')
    if paragraphs:
        text = "\n\n".join(p.text_content() for p in paragraphs)
        text = strip_refs(text)
        text = re.sub(r'</?protect>', '', text)
        text = re.sub(r'\n{3,}', '\n', text).strip()
        if text:
            performer["bio"] = text

    # Image (infobox photo link -> full-res file page)
    img_links = tree.xpath('//table[contains(@class,"infobox")]//a[img]/@href')
    photo_url = None
    if img_links:
        file_page = img_links[0]
        file_page_url = urljoin(BASE, file_page)
        try:
            fp_scraped = session.get(file_page_url, timeout=(5, 10))
            fp_tree = lxml_html.fromstring(fp_scraped.text)
            full_img = fp_tree.xpath('//div[@id="file"]/a/@href')
            if full_img:
                photo_url = urljoin(BASE, full_img[0])
        except Exception:
            pass
        if not photo_url:
            # fallback: raw <img> src straight from the infobox
            img_src = tree.xpath('//table[contains(@class,"infobox")]//img/@src')
            if img_src:
                photo_url = urljoin(BASE, img_src[0])
    if photo_url:
        performer["photo"] = photo_url

    performer["notFound"] = False
    # Standardize image fields
    img = performer.get("photo")
    if img:
        performer["image"] = img
        performer["thumbnail"] = img
        performer["cardThumbnail"] = img
        performer["cover_a"] = img
        performer["cover_b"] = img
    performer["kind"] = "performer"
    return performer


def performer_search(name):
    try:
        scraped = session.get(
            f"{BASE}/wiki/api.php",
            params={"action": "query", "format": "json", "list": "search", "srwhat": "title", "srsearch": name},
            timeout=(5, 10),
        )
        scraped.raise_for_status()
        data = scraped.json()
        results = data.get("query", {}).get("search", [])
        if results:
            performers = [{
                "kind": "performer",
                "name": r.get("title", ""),
                "url": f"{BASE}/boobs/" + re.sub(r'\s', '_', r.get("title", "")),
            } for r in results]
            return {"performers": performers}
    except Exception as e:
        print(f"[boobpedia] Search failed: {e}", file=sys.stderr)
    return {"notFound": True, "query": name}


def scrape(title="", url="", html="", name="", **kwargs):
    """Unified entry point called by the backend."""
    if url:
        return performer_from_url(url)
    query = (title or name or "").strip()
    if query:
        result = performer_search(query)
        if isinstance(result, dict) and 'performers' in result:
            performers = result['performers']
            if performers:
                # Fetch full profile from the first result's URL
                profile_url = performers[0].get('url') or performers[0].get('boobpediaUrl')
                if profile_url:
                    return performer_from_url(profile_url)
                return performers[0]
            return {'notFound': True}
        return result
    return {"error": "need url or title", "notFound": True}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: boobpedia_scraper.py <search|url> <name|url>"}))
        sys.exit(1)

    op = sys.argv[1]
    arg = sys.argv[2]

    try:
        if op == "search":
            result = performer_search(arg)
        elif op == "url":
            result = performer_from_url(arg)
        else:
            result = {"error": f"Unknown operation: {op}"}
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
