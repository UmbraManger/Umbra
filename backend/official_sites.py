"""The studio official-sites catalog used by bulk-fetch web routing.

Ordered list of (domain, studio). Bulk information runs sweep these FIRST —
a hit on an official site's own domain beats whatever aggregator a search
engine returned. A domain is only asked for results when an installed scraper
actually covers it (run_for_site routing decides that), so this list can be
a superset of the bundled scrapers."""

OFFICIAL_SITES = [
    # Jules Jordan network
    ("julesjordan.com", "Jules Jordan"), ("jessicajames.com", "Jules Jordan"),
    ("manuelferrara.com", "Jules Jordan"),
    # Evil Angel / Elegant Angel
    ("evilangel.com", "Evil Angel"), ("elegantangel.com", "Elegant Angel"),
    # Aylo (Project1Service shared API)
    ("brazzers.com", "Brazzers"), ("realitykings.com", "Reality Kings"),
    ("mofos.com", "Mofos"), ("digitalplayground.com", "Digital Playground"),
    ("brazzersnetwork.com", "Brazzers"),
    # LetsDoeIt / FakeHub
    ("fakehub.com", "Fake Hub"), ("fakehostel.com", "Fake Hub"),
    ("fakehospital.com", "Fake Hub"), ("faketaxi.com", "Fake Hub"),
    ("letsdoeit.com", "LetsDoeIt"), ("amateureuro.com", "LetsDoeIt"),
    ("vipsexvault.com", "LetsDoeIt"), ("doe-tv.com", "LetsDoeIt"),
    # Naughty America
    ("naughtyamerica.com", "Naughty America"),
    ("naughtybookworms.com", "Naughty America"), ("naughtyathletics.com", "Naughty America"),
    ("latinaensextension.com", "Naughty America"),
    # Others bundled with Umbra
    ("private.com", "Private"), ("bangbros.com", "BangBros"),
    ("darkkotv.com", "Darkko"), ("pornbox.com", "Pornbox"), ("analvids.com", "AnalVids"),
    ("wicked.com", "Wicked"), ("bang.com", "Bang"),
    ("dogfartnetwork.com", "Dogfart"), ("cuckoldsessions.com", "Dogfart"),
    ("blacksoboys.com", "Dogfart"), ("interracialblowbang.com", "Dogfart"),
    # xEmpire / Vixen / Jules Jordan sister networks etc.
    ("darkx.com", "xCreative"), ("hardx.com", "xCreative"), ("lesbianx.com", "xCreative"),
    ("vixen.com", "Vixen"), ("blacked.com", "Vixen"), ("blackedraw.com", "Vixen"),
    ("tushy.com", "Vixen"), ("tushyraw.com", "Vixen"), ("deeper.com", "Vixen"),
    ("slayed.com", "Vixen"), ("sinsvr.com", "Sins"), ("sweet-pornstars.com", "Sweet Pornstars"),
    # Stores (useful as movie lookup of last resort)
    ("adultempire.com", "Adult Empire"),
]
