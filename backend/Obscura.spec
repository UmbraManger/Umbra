import os

a = Analysis(
    ['main.py'],                    # this spec lives in backend/, so this resolves
    pathex=['.'],
    datas=[
        ('../frontend', 'frontend'),   # server.py serves it from _MEIPASS/frontend
        ('../scrapers', 'scrapers'),   # scraper library -> data/scrapers at startup
    ],
    hiddenimports=[
        # uvicorn
        'uvicorn.logging', 'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        # fastapi + starlette internals
        'fastapi', 'fastapi.responses', 'fastapi.staticfiles',
        'fastapi.middleware.cors', 'starlette', 'starlette.responses',
        'starlette.staticfiles', 'starlette.middleware.cors',
        # core deps
        'requests', 'urllib3', 'charset_normalizer', 'certifi', 'idna',
        'bs4', 'bs4.builder', 'bs4.builder._htmlparser',
        'yaml', 'cryptography', 'cryptography.hazmat.primitives.ciphers.aead',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'keyring', 'keyring.backends',
        'python-multipart', 'multipart',
        'pywebview',
        # pywebview picks its backend by dynamic import, so PyInstaller cannot see
        # it. Ship edgechromium (Win10/11 default) + winforms (fallback); the rest
        # are for other OSes and only bloat the build.
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'tkinter',
        # imported at module scope by server.py
        'pydantic', 'cloudscraper',
        # this project's own lazily-imported modules (see backend/algolia.py etc.)
        'algolia', 'p1api', 'scrape', 'keystore',
        # sqlite
        'sqlite3',
    ],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Obscura',
         console=bool(int(os.environ.get('OBSCURA_CONSOLE', '0'))))
coll = COLLECT(exe, a.binaries, a.datas, name='Obscura')