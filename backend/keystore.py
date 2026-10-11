"""AI API key storage — OS keyring when available (Windows Credential Manager /
macOS Keychain / Linux Secret Service), settings fallback otherwise."""
try:
    import keyring as _kr
    _kr.get_keyring()
    _OK = True
except Exception:
    _OK = False

# Windows Credential Manager key for the image-vault secrets. Do NOT rename to
# match the app: existing installs would lose their stored keys.
SERVICE = "Obscura"
ENTRY = "ai_api_key"

def available() -> bool:
    return _OK

def get_key() -> str | None:
    if not _OK: return None
    try: return _kr.get_password(SERVICE, ENTRY)
    except Exception: return None

def set_key(key: str) -> bool:
    """Empty string deletes the entry."""
    if not _OK: return False
    try:
        if key: _kr.set_password(SERVICE, ENTRY, key)
        else: _kr.delete_password(SERVICE, ENTRY)
        return True
    except Exception:
        return False
