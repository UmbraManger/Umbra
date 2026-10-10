"""Real media serving: HTTP Range streaming, ffprobe metadata,
sidecar subtitles (srt→vtt), OS-default-player launching."""
import os, re, json, mimetypes, subprocess, sys
from collections.abc import Iterator

import db

CHUNK = 1024 * 512

# No console window for child processes — ffprobe pops one black CMD window
# per probe otherwise (see scanner._NO_WIN).
_NO_WIN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

VIDEO_MIME = {
    ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
    ".webm": "video/webm", ".mov": "video/quicktime", ".m4v": "video/mp4",
    ".wmv": "video/x-ms-wmv", ".mpg": "video/mpeg", ".mpeg": "video/mpeg",
    ".ts": "video/mp2t", ".flv": "video/x-flv", ".3gp": "video/3gpp",
}

SUB_EXT = {".srt", ".vtt", ".ass", ".ssa", ".sub"}


class RangeNotSatisfiable(Exception):
    """Requested byte range lies outside the file (HTTP 416)."""


def _table(kind: str) -> str | None:
    return {"movie": "movies", "scene": "scenes"}.get(kind)


def get_path(kind: str, rid: str) -> str | None:
    t = _table(kind)
    if not t:
        return None
    row = db.one(f"SELECT file_path FROM {t} WHERE id=?", (rid,))
    p = row["file_path"] if row else None
    if not p or not os.path.isfile(p):
        return None
    # Containment only when scan folders are known: without any configured
    # folder there is no root to compare against (a record linked before the
    # folders were set up must keep playing — see tests/test_media.py).
    roots = scan_roots()
    if roots and not inside_roots(p, roots):
        return None
    return p


def scan_roots() -> list[str]:
    """Normalized real paths of the configured scan folders (empty = none)."""
    return [os.path.realpath(r) for r in (db.get_settings().get("dirs") or [])
            if isinstance(r, str) and r]


def inside_roots(path: str, roots: list[str]) -> bool:
    """True when path resolves to one of the roots or anything beneath it."""
    p = os.path.normcase(os.path.realpath(path))
    for r in roots:
        r = os.path.normcase(r)
        if p == r or p.startswith(r + os.sep):
            return True
    return False


def mime_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_MIME:
        return VIDEO_MIME[ext]
    guessed = mimetypes.guess_type(path)[0] or ""
    # Only ever label responses as video: anything else (text/html!) must fall
    # back to octet-stream so a stored page can't be rendered from our origin.
    if guessed.startswith("video/"):
        return guessed
    return "application/octet-stream"


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Parse an HTTP Range header (single range).

    Returns (start, end) inclusive, or None when the header is absent/unsupported.
    Raises RangeNotSatisfiable when the range lies outside the file, so the
    caller can answer 416 instead of silently sending the whole file (which
    breaks seeking in players).
    """
    if not header:
        return None
    m = re.match(r"bytes=(\d*)-(\d*)$", header.strip())
    if not m or (not m.group(1) and not m.group(2)):
        return None
    if size <= 0:
        raise RangeNotSatisfiable()
    if not m.group(1):
        # suffix range: last N bytes
        n = int(m.group(2))
        if n <= 0:
            raise RangeNotSatisfiable()
        start, end = max(0, size - n), size - 1
    else:
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
    if start >= size or end < start:
        raise RangeNotSatisfiable()
    return start, min(end, size - 1)


def iter_file(path: str, start: int = 0, length: int = 0) -> Iterator[bytes]:
    """Yield file chunks for streaming. If length=0, stream the whole file."""
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length if length > 0 else os.path.getsize(path) - start
        while remaining > 0:
            chunk = f.read(min(CHUNK, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def probe(path: str) -> dict:
    """Get media info via ffprobe. Returns a dict with duration, resolution, etc."""
    info = {"path": path, "duration": 0, "width": 0, "height": 0, "codec": "", "bitrate": 0}
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, timeout=15, creationflags=_NO_WIN)
        if r.returncode != 0:
            return info
        j = json.loads(r.stdout.decode("utf-8", "ignore"))
        fmt = j.get("format", {})
        info["duration"] = float(fmt.get("duration", 0) or 0)
        info["bitrate"] = int(fmt.get("bit_rate", 0) or 0)
        for s in j.get("streams", []):
            if s.get("codec_type") == "video":
                info["width"] = int(s.get("width", 0) or 0)
                info["height"] = int(s.get("height", 0) or 0)
                info["codec"] = s.get("codec_name", "")
                break
    except Exception:
        pass
    return info


def sidecar_subs(path: str) -> list:
    """Find subtitle files next to the video file.

    A subtitle belongs to the video when its own stem EQUALS the video stem or
    extends it with a dot-suffix ('movie.en.srt', 'movie.forced.srt'). A plain
    substring test would make 'a.mp4' pick up 'banana.srt' (bug D5).
    """
    d = os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    subs = []
    try:
        for f in sorted(os.listdir(d)):
            ext = os.path.splitext(f)[1].lower()
            if ext not in SUB_EXT:
                continue
            sub_stem = os.path.splitext(f)[0].lower()
            if stem and (sub_stem == stem or sub_stem.startswith(stem + ".")):
                subs.append({"file": os.path.join(d, f), "name": f, "ext": ext})
            elif not stem:
                subs.append({"file": os.path.join(d, f), "name": f, "ext": ext})
    except OSError:
        pass
    return subs


def srt_to_vtt(path: str) -> bytes:
    """Convert an SRT subtitle file to WebVTT (a .vtt input is passed through
    with a single header — it used to be wrapped in a second WEBVTT, bug D5)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    content = content.lstrip("\ufeff")
    # Replace SRT timestamp format (comma) with VTT format (dot)
    content = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", content)
    body = content.strip()
    if body[:6].upper() == "WEBVTT":
        return (body + "\n").encode("utf-8")
    return ("WEBVTT\n\n" + body + "\n").encode("utf-8")


def open_with_os(path: str) -> bool:
    """Open a media file with the OS default player."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False

def reveal_in_os(path: str) -> bool:
    """Open the file explorer and select the file."""
    try:
        if sys.platform == "win32":
            # arg list + shell=False: a crafted filename must never become shell syntax
            subprocess.Popen(["explorer", "/select,", os.path.normcase(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
        return True
    except Exception:
        return False
