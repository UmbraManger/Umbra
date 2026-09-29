a = Analysis(
    ['main.py'],
    pathex=['.'],
    datas=[('frontend', 'frontend')],
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
        'tkinter',
        # sqlite
        'sqlite3',
    ],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Obscura', console=False)
coll = COLLECT(exe, a.binaries, a.datas, name='Obscura')