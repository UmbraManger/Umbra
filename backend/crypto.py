"""Image protection — AES-256-GCM per image, key derived with Argon2id
(PBKDF2-SHA256 @ 600k fallback). Passphrase verification uses an AEAD
verifier, NOT a fast hash, so imgprot.json is no longer an offline
dictionary oracle.

Meta format (v2, imgprot.json):
    {"on": bool, "pass_set": bool,
     "salt":   "<hex 16 bytes>",
     "kdf":    {"type": "argon2id", "time_cost": 3,
                "memory_cost": 65536, "lanes": 4}
            | {"type": "pbkdf2", "iterations": 600000},
     "verifier": {"iv": "<hex>", "ct": "<hex>"}}

Legacy v1 meta ({"salt", "hash", ...}: SHA-256 oracle + PBKDF2-150k) is still
readable — unlock()/set_passphrase() accept it and transparently upgrade the
record to v2 *keeping the same derived key*, so existing blobs stay valid.

Encrypted blob layout (unchanged): <12-byte IV><AES-GCM ciphertext+tag>.
"""
import os, re, json, shutil, hashlib
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
import db

ENC_DIR = os.path.join(db.DATA_DIR, "encrypted")
META    = os.path.join(db.DATA_DIR, "imgprot.json")

# Image ids are generated as "i" + 4 random bytes hex — enforce it everywhere so
# URL params can never traverse out of ENC_DIR.
IMG_ID_RE = re.compile(r"^i[0-9a-f]{8}$")

# Known plaintext encrypted under the derived key: decryption success == correct
# passphrase. Nothing fast to brute-force is stored.
_VERIFIER_PT = b"obscura-image-protection-verifier-v2"

KDF_PBKDF2_STRONG = {"type": "pbkdf2", "iterations": 600000}
KDF_PBKDF2_LEGACY = {"type": "pbkdf2", "iterations": 150000}  # v1 blobs/meta

# Only these ever leave load_image()/store_image() as a response Content-Type.
_SAFE_MIMES = ("image/jpeg", "image/png", "image/webp", "image/gif")


class Locked(Exception):
    pass


class MetaError(Exception):
    """imgprot.json exists but is unreadable/corrupt — refusing to guess."""


class IntegrityError(Exception):
    """Blob failed GCM authentication (corrupt/tampered), NOT a locked vault."""


# ---------------------------------------------------------------- meta ----
def _meta() -> dict:
    try:
        with open(META, encoding="utf-8") as f:
            m = json.load(f)
    except FileNotFoundError:
        # Never configured — "protection off" is the correct answer.
        return {"on": False, "salt": "", "pass_set": False}
    except Exception as e:
        # A corrupt/locked meta must NEVER read as "protection off": callers
        # would write plaintext and set_enabled() would overwrite the real
        # salt/verifier with a synthesized default, destroying the vault.
        raise MetaError(
            f"image-protection meta {META} is unreadable or corrupt ({e}) — "
            f"repair it or restore {META}.bak; refusing to guess") from e
    if not isinstance(m, dict):
        raise MetaError(f"image-protection meta {META} is corrupt (not a JSON object)")
    return m


def _save_meta(m: dict) -> None:
    os.makedirs(db.DATA_DIR, exist_ok=True)
    if os.path.exists(META):
        # Keep one generation of the real meta (salt/verifier) before any
        # legitimate rewrite, so a later corruption is recoverable.
        try:
            shutil.copy2(META, META + ".bak")
        except OSError:
            pass
    tmp = META + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f)
    os.replace(tmp, META)


def _blob_meta_path(img_id: str) -> str:
    return os.path.join(ENC_DIR, img_id + ".json")


def _blob_path(img_id: str) -> str:
    return os.path.join(ENC_DIR, img_id + ".bin")


# ----------------------------------------------------------------- kdf ----
def _best_kdf() -> dict:
    """Argon2id when the cryptography build supports it, else strong PBKDF2."""
    if _argon2_available():
        return {"type": "argon2id", "time_cost": 3,
                "memory_cost": 65536, "lanes": 4}
    return dict(KDF_PBKDF2_STRONG)


def _argon2_available() -> bool:
    try:
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id  # noqa: F401
        return True
    except Exception:
        return False


def _derive(pw: str, salt: bytes, kdf: dict) -> bytes:
    kdf = kdf or KDF_PBKDF2_STRONG
    if kdf.get("type") == "argon2id":
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
        return Argon2id(
            salt=salt, length=32,
            iterations=int(kdf.get("time_cost", 3)),
            lanes=int(kdf.get("lanes", 4)),
            memory_cost=int(kdf.get("memory_cost", 65536)),
        ).derive(pw.encode())
    it = int(kdf.get("iterations", KDF_PBKDF2_STRONG["iterations"]))
    k = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=it)
    return k.derive(pw.encode())


def _legacy_sha(s: str) -> str:
    """v1-only: kept *solely* to read old meta. Never written again."""
    return hashlib.sha256(("obscura::" + s).encode()).hexdigest()


# ------------------------------------------------------------ verifier ----
def _verifier_make(key: bytes) -> dict:
    iv = os.urandom(12)
    return {"iv": iv.hex(), "ct": AESGCM(key).encrypt(iv, _VERIFIER_PT, None).hex()}


def _verifier_check(key: bytes, v: dict) -> bool:
    try:
        pt = AESGCM(key).decrypt(bytes.fromhex(v["iv"]), bytes.fromhex(v["ct"]), None)
        return pt == _VERIFIER_PT
    except Exception:
        return False


def _key_for_passphrase(pw: str, m: dict) -> bytes | None:
    """Derive and verify a passphrase against meta. None == wrong passphrase."""
    if not m.get("pass_set"):
        return None
    try:
        salt = bytes.fromhex(m.get("salt") or "")
    except ValueError:
        return None
    if not salt:
        return None
    if m.get("verifier"):
        key = _derive(pw, salt, m.get("kdf") or KDF_PBKDF2_STRONG)
        return key if _verifier_check(key, m["verifier"]) else None
    # legacy v1 meta: fast-hash check, PBKDF2-150k key
    if _legacy_sha(pw) == m.get("hash"):
        return _derive(pw, salt, KDF_PBKDF2_LEGACY)
    return None


def _upgrade_meta_if_legacy(m: dict, key: bytes) -> None:
    """v1 -> v2 meta, same derived key (no blob re-encryption needed)."""
    if m.get("verifier"):
        return
    out = {"on": bool(m.get("on")), "pass_set": True,
           "salt": m.get("salt"), "kdf": dict(KDF_PBKDF2_LEGACY),
           "verifier": _verifier_make(key)}
    _save_meta(out)


# -------------------------------------------------------------- public ----
_state = {"key": None}


def status() -> dict:
    m = _meta()
    return {"on": m.get("on", False), "pass_set": m.get("pass_set", False),
            "unlocked": _state["key"] is not None}


def set_enabled(on: bool) -> dict:
    # _meta() raises MetaError on a corrupt file, so this can never overwrite
    # real-but-unreadable key material with a synthesized default.
    m = _meta(); m["on"] = bool(on); _save_meta(m)
    return status()


def set_passphrase(new_pw: str, current_pw: str | None = None) -> dict:
    """Set/replace the passphrase and re-key every blob.

    Two-phase: everything is decrypted into memory first — a wrong current
    passphrase or an undecryptable blob aborts the operation *before* anything
    on disk is touched, and the failure names the offending files instead of
    silently orphaning them. Plain blobs are folded into the encrypted set.
    """
    if not new_pw:
        raise ValueError("passphrase must not be empty")
    m = _meta()
    old_key = None
    if m.get("pass_set"):
        old_key = _key_for_passphrase(current_pw or "", m)
        if old_key is None:
            raise ValueError("wrong current passphrase")

    new_salt = os.urandom(16)
    kdf = _best_kdf()
    new_key = _derive(new_pw, new_salt, kdf)

    # ---- phase 1: decrypt/collect (nothing written yet) ----
    pending = []   # (bin_path, meta_path, mime, plaintext)
    if os.path.isdir(ENC_DIR):
        for fn in sorted(os.listdir(ENC_DIR)):
            if not fn.endswith(".bin"):
                continue
            bp = os.path.join(ENC_DIR, fn)
            mp = bp[:-4] + ".json"
            bm = {}
            if os.path.exists(mp):
                try:
                    with open(mp, encoding="utf-8") as f:
                        bm = json.load(f)
                except Exception:
                    bm = {}
            with open(bp, "rb") as f:
                blob = f.read()
            if bm.get("enc"):
                if old_key is None:
                    raise ValueError(f"{fn} is encrypted but no valid current passphrase was given")
                try:
                    pt = AESGCM(old_key).decrypt(blob[:12], blob[12:], None)
                except Exception:
                    raise ValueError(
                        f"{fn} could not be decrypted with the current passphrase — "
                        "re-key aborted, nothing was changed")
            else:
                # Sidecar says plaintext (or is missing/corrupt). If the bytes
                # are already GCM ciphertext under the current key, encrypting
                # them again would nest ciphertext unrecoverably — refuse.
                if old_key is not None and _is_ciphertext(old_key, blob):
                    raise ValueError(
                        f"{fn} is already encrypted but its metadata is missing/corrupt — "
                        "fix the sidecar before re-keying (nothing was changed)")
                pt = blob  # plain blob -> will be encrypted below
            pending.append((bp, mp, _safe_mime(bm.get("mime")), pt))

    # ---- phase 2: rewrite (tmp + atomic replace, originals backed up) ----
    if pending:
        bak = os.path.join(ENC_DIR, ".rekey-backup")
        shutil.rmtree(bak, ignore_errors=True)
        os.makedirs(bak, exist_ok=True)
        try:
            for bp, mp, mime, pt in pending:
                for src in (bp, mp):
                    if os.path.exists(src):
                        shutil.copy2(src, os.path.join(bak, os.path.basename(src)))
                iv = os.urandom(12)
                tmp = bp + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(iv + AESGCM(new_key).encrypt(iv, pt, None))
                os.replace(tmp, bp)
                _write_blob_meta(mp, {"mime": mime, "enc": True})
        except Exception:
            # originals kept in .rekey-backup for manual recovery
            raise
        shutil.rmtree(bak, ignore_errors=True)

    _save_meta({"on": True, "pass_set": True, "salt": new_salt.hex(),
                "kdf": kdf, "verifier": _verifier_make(new_key)})
    _state["key"] = new_key
    return status()


def unlock(pw: str) -> bool:
    m = _meta()
    if not m.get("pass_set"):
        return False
    key = _key_for_passphrase(pw, m)
    if key is None:
        return False
    _upgrade_meta_if_legacy(m, key)
    _state["key"] = key
    return True


def encrypt_plaintext() -> int:
    """Re-encrypt blobs stored as plaintext (protection was off/locked then).

    Requires image protection enabled and unlocked. Returns the count."""
    m = _meta()
    if not (m.get("on") and m.get("pass_set")):
        raise ValueError("image protection is not enabled")
    key = _state["key"]
    if not key:
        raise Locked()
    n = 0
    if not os.path.isdir(ENC_DIR):
        return 0
    for fn in sorted(os.listdir(ENC_DIR)):
        if not fn.endswith(".bin"):
            continue
        bp = os.path.join(ENC_DIR, fn)
        mp = bp[:-4] + ".json"
        bm = {}
        if os.path.exists(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    bm = json.load(f)
            except Exception:
                bm = {}
        if bm.get("enc"):
            continue
        with open(bp, "rb") as f:
            pt = f.read()
        if _is_ciphertext(key, pt):
            # Sidecar lost/corrupt but the blob is already ciphertext — do NOT
            # encrypt it again (that would corrupt it irrecoverably).
            raise ValueError(
                f"{fn} is already encrypted but its metadata is missing/corrupt — "
                "fix the sidecar instead of re-encrypting (nothing was changed)")
        iv = os.urandom(12)
        tmp = bp + ".tmp"
        with open(tmp, "wb") as f:
            f.write(iv + AESGCM(key).encrypt(iv, pt, None))
        os.replace(tmp, bp)
        _write_blob_meta(mp, {"mime": _safe_mime(bm.get("mime")), "enc": True})
        n += 1
    return n


def store_image(data: bytes, mime: str) -> str:
    os.makedirs(ENC_DIR, exist_ok=True)
    m = _meta()
    on = bool(m.get("on") and m.get("pass_set"))
    key = _state["key"]
    if on and not key:
        # Never silently write plaintext when protection is on: the caller gets
        # a Locked error instead of a file that quietly dodges the vault.
        raise Locked("image protection is on but locked — unlock before adding images")
    img_id = "i" + os.urandom(4).hex()
    meta = {"mime": _safe_mime(mime), "enc": bool(on)}
    tmp = _blob_path(img_id) + ".tmp"
    with open(tmp, "wb") as f:
        if on:
            iv = os.urandom(12)
            f.write(iv + AESGCM(key).encrypt(iv, data, None))
        else:
            f.write(data)
    # Blob first, sidecar last: a hard crash in between leaves a sidecar-less
    # blob (never a dangling sidecar). If the sidecar write *fails*, remove the
    # blob too so no orphan can later be mistaken for plaintext and re-encrypted.
    try:
        os.replace(tmp, _blob_path(img_id))
        _write_blob_meta(_blob_meta_path(img_id), meta)
    except Exception:
        for p in (_blob_path(img_id), _blob_meta_path(img_id)):
            try: os.remove(p)
            except OSError: pass
        raise
    return img_id


def load_image(img_id: str) -> tuple[bytes, str] | None:
    if not IMG_ID_RE.fullmatch(img_id or ""):
        return None
    bp, mp = _blob_path(img_id), _blob_meta_path(img_id)
    if not os.path.exists(bp):
        return None
    meta = {}
    if os.path.exists(mp):
        try:
            with open(mp, encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    with open(bp, "rb") as f:
        blob = f.read()
    if meta.get("enc"):
        if not _state["key"]:
            raise Locked()
        if len(blob) < 28:  # 12-byte IV + 16-byte GCM tag
            raise IntegrityError(f"image {img_id} is truncated — cannot authenticate")
        try:
            data = AESGCM(_state["key"]).decrypt(blob[:12], blob[12:], None)
        except InvalidTag as e:
            # Tampering/corruption is NOT a locked vault — report it as such.
            raise IntegrityError(
                f"image {img_id} failed GCM authentication — corrupt or tampered with") from e
        except Exception:
            raise Locked()
    else:
        data = blob
    return data, _safe_mime(meta.get("mime"))


def remove_image(img_id: str) -> None:
    """Delete an image's blob + metadata (used when its record is deleted)."""
    if not IMG_ID_RE.fullmatch(img_id or ""):
        return
    for suffix in (".bin", ".json"):
        try:
            os.remove(os.path.join(ENC_DIR, img_id + suffix))
        except OSError:
            pass


# --------------------------------------------------------------- utils ----
def _safe_mime(m) -> str:
    """Sidecar mimes are unauthenticated — only an allowlist may become a
    response Content-Type (anything else falls back to image/jpeg)."""
    return m if isinstance(m, str) and m.lower() in _SAFE_MIMES else "image/jpeg"


def _is_ciphertext(key: bytes, blob: bytes) -> bool:
    """True when blob is already AES-GCM ciphertext under key (used to refuse
    double-encryption). False-positive chance is the GCM forgery probability."""
    if len(blob) < 28:
        return False
    try:
        AESGCM(key).decrypt(blob[:12], blob[12:], None)
        return True
    except Exception:
        return False


def _write_blob_meta(path: str, meta: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    os.replace(tmp, path)
