"""Best-match selection for search-by-title scrapers.

Windows filenames cannot carry ':' '|' '?''*' etc., so imported titles often
differ from the site's exact wording. Sites' search APIs still return the
right hit, but scrapers that blindly take the first result pick the wrong
scene. coverage() scores how much of the query's tokens the candidate title
covers — pick that, not result order."""
import re


def tokens(s):
    # Apostrophes vanish (or get mute-widowed) going from a website title into a
    # Windows filename: "Sophie's" → "Sophie s" / "Sophies" — dropping the "'"
    # glues both sides into the same token.
    return set(re.findall(r"[a-z0-9]+", (s or "").lower().replace("'", "")))


def coverage(query, candidate_title):
    q = tokens(query)
    t = tokens(candidate_title)
    return len(q & t) / len(q) if q else 0.0


def best(candidates, query, key="title"):
    """Highest-coverage candidate, or the list untouched when it is not a list."""
    if not isinstance(candidates, list) or len(candidates) < 2:
        return candidates
    rank = lambda c: coverage(query, (c or {}).get(key) or "")
    winner = max(candidates, key=rank)
    # A candidate covering none of the query is a wrong-hits fallback; then the
    # site's own order is as good a guess as ours.
    return winner if rank(winner) >= 0.5 else candidates[0]
