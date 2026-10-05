#!/usr/bin/env python3
"""Babepedia scraper — adapted from stashapp/CommunityScrapers.
Usage:
  python3 babepedia_scraper.py search "Name"
  python3 babepedia_scraper.py url "https://www.babepedia.com/babe/Name"
"""

import json
import re
import sys
from datetime import datetime
from urllib.parse import urljoin

import cloudscraper
from lxml import html as lxml_html

# Use cloudscraper to bypass Cloudflare
session = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
# Warm up Cloudflare session by visiting main page first
try:
    _warmup = session.get('https://www.babepedia.com/', timeout=(5, 10))
    print(f"[babepedia] Warm-up status: {_warmup.status_code}", file=sys.stderr)
except Exception as _e:
    print(f"[babepedia] Warm-up failed: {_e}", file=sys.stderr)


def biography_xpath_test(tree, html_name, selector):
    elem = tree.xpath(f'//span[contains(text(), "{html_name}")]/following-sibling::span{selector}/text()')
    return elem[0].strip() if elem else None


def sanitize_ethnicity(s):
    s_upper = s.upper()
    if s_upper in ["CAUCASIAN", "BLACK", "ASIAN", "INDIAN", "LATIN", "MIDDLE_EASTERN", "MIXED", "OTHER"]:
        return s_upper
    if "MIXED" in s_upper:
        return s_upper
    return s


def sanitize_hair_color(s):
    if s.lower() == "brown":
        return "Brunette"
    return s


def performer_from_url(url):
    scraped = session.get(url, timeout=(5, 15))
    scraped.raise_for_status()
    tree = lxml_html.fromstring(scraped.text)

    # Name
    name_el = tree.xpath('//h1[@id="babename"]')
    if not name_el:
        return {"notFound": True, "url": url}
    name = name_el[0].text.strip()

    performer = {"name": name, "babepediaUrl": url}

    # Aliases
    aliases = tree.xpath('//h2[@id="aka"][1]/text()')
    if aliases:
        performer["aliases"] = ", ".join(a.strip() for a in aliases[0].strip().split(" - ") if a.strip())

    # Birthdate
    birth_container = tree.xpath('//span[contains(text(), "Born:")]/following-sibling::span/a')
    if birth_container:
        if len(birth_container) == 2:
            birth_text = list(map(lambda x: x.text_content().strip(), birth_container))
            birth_date = " ".join(birth_text)
            clean_birth_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', birth_date)
            try:
                birthdate = datetime.strptime(clean_birth_date, "%d of %B %Y").date()
                performer["birthday"] = birthdate.strftime("%B %d, %Y")
            except ValueError:
                performer["birthday"] = clean_birth_date
        elif len(birth_container) == 1:
            performer["birthday"] = birth_container[0].text_content().strip()

    # Death date
    death_date = biography_xpath_test(tree, "Died", "")
    if death_date:
        clean = re.sub(r'\w+ (\d+)(?:st|nd|rd|th) of (\w+) (\d+) \(.+\)', r'\1 \2 \3', death_date)
        try:
            performer["deathDate"] = datetime.strptime(clean, "%d %B %Y").date().isoformat()
        except ValueError:
            performer["deathDate"] = clean

    # Career length
    career = biography_xpath_test(tree, "Years active", "")
    if career:
        years = career.split(" ", 1)[0]
        parts = years.split("-")
        if len(parts) == 2:
            start, end = parts
            performer["activeYears"] = f"{start} - {end}" if end != "Present" else f"{start} - "

    # Nationality (from flag icon class)
    nationality_flags = tree.xpath('//span[contains(text(), "Nationality")]/following-sibling::span//span[contains(@class, "fi-")]/@class')
    if nationality_flags:
        m = re.search(r'fi fi-([a-z]{2})', nationality_flags[0])
        if m:
            performer["nationality"] = m.group(1).upper()

    # Ethnicity
    ethnicity = biography_xpath_test(tree, "Ethnicity", "/a")
    if ethnicity:
        performer["ethnicity"] = sanitize_ethnicity(ethnicity)

    # Eye color
    eye_color = biography_xpath_test(tree, "Eye color", "/a")
    if eye_color:
        performer["eyeColor"] = eye_color

    # Hair color
    hair_color = biography_xpath_test(tree, "Hair color", "/a")
    if hair_color:
        performer["hairColor"] = sanitize_hair_color(hair_color)

    # Height
    height = biography_xpath_test(tree, "Height", "")
    if height:
        cm = re.search(r'(\d+) cm', height)
        if cm:
            performer["height"] = int(cm.group(1))

    # Weight
    weight = biography_xpath_test(tree, "Weight", "")
    if weight:
        kg = re.search(r'(\d+) kg', weight)
        if kg:
            performer["weight"] = int(kg.group(1))

    # Measurements
    measurements = biography_xpath_test(tree, "Measurements", "")
    cup_size = biography_xpath_test(tree, "Bra/cup size", "")
    if measurements:
        m = re.search(r'(?P<band>\d+)(?:–|-)(?P<waist>\d+)(?:–|-)(?P<hip>\d+)', measurements)
        if cup_size and m:
            _, waist_size, hip_size = m.groups()
            performer["measurements"] = f"{cup_size}-{waist_size}-{hip_size}"
        else:
            performer["measurements"] = measurements.removesuffix(" (")

    # Boobs
    breast_type = (biography_xpath_test(tree, "Boobs", "/a") or
                   biography_xpath_test(tree, "Breasts", "/a") or
                   biography_xpath_test(tree, "Boobs", "") or
                   biography_xpath_test(tree, "Breasts", "") or
                   biography_xpath_test(tree, "Implants", "/a") or
                   biography_xpath_test(tree, "Implants", ""))
    import sys
    print(f"[babepedia] Boobs raw value: {breast_type}", file=sys.stderr)
    if breast_type:
        bt = breast_type.lower()
        if "real" in bt or "natural" in bt:
            performer["boobs"] = "Natural"
        elif "fake" in bt or "implant" in bt or "silicone" in bt or "saline" in bt:
            performer["boobs"] = "Enhanced"
        else:
            performer["boobs"] = breast_type

    # Tattoos
    tattoos = biography_xpath_test(tree, "Tattoos", "")
    if tattoos and tattoos.lower() != "none":
        performer["tattoos"] = tattoos

    # Piercings
    piercings = biography_xpath_test(tree, "Piercings", "")
    if piercings and piercings.lower() != "none":
        performer["piercings"] = piercings

    # Bio
    bio = tree.xpath('//p[@id="biotext"]')
    if bio:
        performer["bio"] = bio[0].text_content().strip()

    # Social URLs — parse specific platforms
    social_urls = tree.xpath('//div[@id="socialicons"]/a/@href')
    onlyfans_links = []
    for href in social_urls:
        low = href.lower()
        if 'twitter.com' in low or 'x.com' in low:
            handle = href.rstrip('/').split('/')[-1]
            if handle and handle not in ('twitter', 'x', 'com', 'intent', 'status'):
                performer['twitter'] = '@' + handle
        elif 'instagram.com' in low:
            handle = href.rstrip('/').split('/')[-1]
            if handle and handle not in ('instagram', 'com', 'accounts', 'p', 'explore'):
                performer['instagram'] = '@' + handle
        elif 'onlyfans.com' in low or '/onlyfans/' in low:
            # Resolve the full OnlyFans URL
            if href.startswith('/onlyfans/') or href.startswith('https://www.babepedia.com/onlyfans/'):
                if '/onlyfans/' in href:
                    slug = href.split('/onlyfans/')[-1].strip('/ ')
                else:
                    slug = href.rstrip('/').split('/')[-1]
                if slug:
                    onlyfans_links.append(('https://onlyfans.com/' + slug, slug))
            else:
                handle = href.rstrip('/').split('/')[-1]
                if handle and handle not in ('onlyfans', 'com'):
                    onlyfans_links.append((href.rstrip('/'), handle))
        elif href.startswith('http'):
            performer.setdefault('urls', []).append(href)
    # Prefer paid OnlyFans (slug without 'free' in it) over free
    if onlyfans_links:
        paid = [(u, s) for u, s in onlyfans_links if 'free' not in s.lower()]
        chosen_slug = paid[0][1] if paid else onlyfans_links[0][1]
        performer['onlyfans'] = chosen_slug

    # Photo
    main_imgs = tree.xpath('//div[@id="profbox2"]//a[@class="img"]/@href')
    if main_imgs:
        performer["photo"] = urljoin("https://www.babepedia.com", main_imgs[0])
    else:
        # fallback: profile image
        profile_img = tree.xpath('//div[@id="profbox2"]//img/@src')
        if profile_img:
            performer["photo"] = urljoin("https://www.babepedia.com", profile_img[0])

    performer["notFound"] = False
    return performer


def performer_search(name):
    import sys
    search_name = name.replace("-", " ")
    print(f"[babepedia] Searching for: {search_name}", file=sys.stderr)
    # Try AJAX endpoint first
    try:
        scraped = session.get("https://www.babepedia.com/ajax-search.php", params={"term": search_name}, timeout=(5, 10))
        print(f"[babepedia] AJAX search status: {scraped.status_code}", file=sys.stderr)
        if scraped.status_code == 200:
            data = scraped.json()
            print(f"[babepedia] AJAX search data: {data}", file=sys.stderr)
            if data:
                results = [{
                    "name": item.get("label", ""),
                    "babepediaUrl": f"https://www.babepedia.com/babe/{item.get('value', '').replace(' ', '_')}",
                } for item in data]
                return {"performers": results}
    except Exception as e:
        print(f"[babepedia] AJAX search failed: {e}", file=sys.stderr)
    # Fallback: scrape search results page directly
    try:
        url = f"https://www.babepedia.com/results/{search_name.replace(' ', '_')}"
        print(f"[babepedia] Trying search page: {url}", file=sys.stderr)
        scraped = session.get(url, timeout=(5, 15))
        scraped.raise_for_status()
        tree = lxml_html.fromstring(scraped.text)
        names = tree.xpath('//div[@class="gallerybox"]//div[@class="galtitle"]/a/text()')
        hrefs = tree.xpath('//div[@class="gallerybox"]//div[@class="galtitle"]/a/@href')
        print(f"[babepedia] Search page found {len(names)} results", file=sys.stderr)
        if names:
            results = [{
                "name": n.strip(),
                "babepediaUrl": urljoin("https://www.babepedia.com", h),
            } for n, h in zip(names, hrefs)]
            return {"performers": results}
    except Exception as e:
        print(f"[babepedia] Search page failed: {e}", file=sys.stderr)
    # Fallback: try direct URL construction (bypasses search)
    try:
        direct_url = f"https://www.babepedia.com/babe/{search_name.replace(' ', '_')}"
        print(f"[babepedia] Trying direct URL: {direct_url}", file=sys.stderr)
        scraped = session.get(direct_url, timeout=(5, 15))
        if scraped.status_code == 200:
            tree = lxml_html.fromstring(scraped.text)
            h1 = tree.xpath('//h1[@id="babename"]')
            if h1:
                found_name = h1[0].text_content().strip()
                print(f"[babepedia] Direct URL found: {found_name}", file=sys.stderr)
                return {"performers": [{"name": found_name, "babepediaUrl": direct_url}]}
        print(f"[babepedia] Direct URL returned {scraped.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"[babepedia] Direct URL failed: {e}", file=sys.stderr)
    print(f"[babepedia] No results found for: {name}", file=sys.stderr)
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
                profile_url = performers[0].get('babepediaUrl') or performers[0].get('url')
                if profile_url:
                    return performer_from_url(profile_url)
                return performers[0]
            return {'notFound': True}
        return result
    return {"error": "need url or title", "notFound": True}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: babepedia_scraper.py <search|url> <name|url>"}))
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
