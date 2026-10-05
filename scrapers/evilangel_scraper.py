"""EvilAngel scraper — uses Algolia API."""
import json, sys
import algolia

SITE_URL = "https://www.evilangel.com"
REFERER = "https://www.evilangel.com/"


def scrape(title="", url="", html="", kind="", **kwargs):
    if url:
        if '/pornstar/' in url or '/model/' in url:
            return _performer_url(url)
        return algolia.scene_by_url(url, SITE_URL, REFERER)
    if title:
        if kind == 'performer':
            return algolia.search_performer(title, SITE_URL, REFERER)
        results = algolia.search_scenes(title, SITE_URL, REFERER)
        if isinstance(results, list) and results:
            best = results[0]
            if best.get('_score', 0) > 0:
                best.pop('_score', None)
                return best
            # Try performer name extraction
            words = title.split()
            for n in (2, 3):
                if len(words) <= n:
                    break
                perf_results = algolia.search_scenes(' '.join(words[:n]), SITE_URL, REFERER)
                if isinstance(perf_results, list) and perf_results:
                    for s in perf_results:
                        if algolia.title_match_score(title, s.get('title', '')) > 0:
                            s.pop('_score', None)
                            return s
            if isinstance(results, list) and results:
                for r in results:
                    r.pop('_score', None)
                return results[0]
        return results if isinstance(results, dict) else {'notFound': True}
    return {}


def _performer_url(url):
    import re
    m = re.search(r'/(\d+)$', url)
    if m:
        creds = algolia.get_algolia_creds(SITE_URL)
        if creds:
            r = algolia.algolia_search(creds, '', index='all_actors',
                                       filters=f'actor_id:{m.group(1)}', hits_per_page=1, referer=REFERER)
            hits = r.get('hits', [])
            if hits:
                return algolia.performer_from_hit(hits[0])
    return {'notFound': True}


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python evilangel_scraper.py <search|url> <query_or_url>')
        sys.exit(1)
    op, arg = sys.argv[1], sys.argv[2]
    if op == 'search':
        print(json.dumps(algolia.search_scenes(arg, SITE_URL, REFERER), indent=2))
    elif op == 'url':
        print(json.dumps(algolia.scene_by_url(arg, SITE_URL, REFERER), indent=2))
    else:
        print(json.dumps({'error': f'Unknown op: {op}'}))
