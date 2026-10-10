"""Obscura entry point — starts the API server, then opens a native window.

The HTTP server is the transport pywebview renders (http://127.0.0.1:<port>); it
is not a "browser mode". To debug the UI in your own browser instead, run:

    python main.py --browser   # DEBUG ONLY — opens your default browser
"""
import sys, os, time, socket, threading, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from server import app, API_TOKEN
import db
import crypto


def _apply_startup_lock() -> None:
    """If the previous session ended with the vault locked, refuse to serve
    until the user unlocks — the dialog is the only way out."""
    m = db.get_settings().get("lock") or {}
    if m.get("on") and m.get("hash"):
        crypto.set_locked(True)

def find_port(start=8765) -> int:
    for p in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p)); return p
            except OSError:
                continue
    return start


def caption_colors():
    """(title-bar bg, title-bar text) for the current theme, as '#rrggbb'.

    Follows the theme plus any Settings › Background swatch, so the native
    caption blends with the app instead of standing out against it.
    """
    bg, fg = "#100e0a", "#ece4d3"          # dark "Ink & Amber"
    try:
        s = db.get_settings()
        if s.get("theme") == "light":
            bg, fg = "#f1ecdf", "#26200f"  # light "Paper & Bronze"
        adv = s.get("adv") or {}           # theme itself is a flat string
        if adv.get("background"):
            c = str(adv["background"]).strip().lstrip("#")
            if len(c) == 3:
                c = "".join(ch * 2 for ch in c)
            if len(c) == 6:
                bg = "#" + c.lower()       # a Settings › Background swatch
    except Exception:
        pass
    return bg, fg


def colorref(h: str):
    """'#rrggbb' (or '#rgb') → Windows COLORREF 0x00BBGGRR, else None.

    Returns None instead of raising: a stray value in settings must not take
    the whole caption repaint down with it (that bug left the bar white).
    """
    try:
        c = h.lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        if len(c) != 6:
            return None
        r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
        return (b << 16) | (g << 8) | r
    except Exception:
        return None


def is_dark(h: str) -> bool:
    """Perceived brightness of '#rrggbb' — decides the fallback caption style."""
    c = colorref(h)
    if c is None:
        return True
    r, g, b = c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF
    return (r * 299 + g * 587 + b * 114) // 1000 < 128

def main():
    port = find_port()
    url = f"http://127.0.0.1:{port}"
    # A windowed (console=False) build has no sys.stderr/sys.stdout, and uvicorn's
    # default formatter calls .isatty() on them -> AttributeError at startup. Point
    # the streams at a null device so access is valid instead of None.
    if getattr(sys, "frozen", False) and sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if getattr(sys, "frozen", False) and sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning",
                            access_log=False)
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()

    import urllib.request
    for _ in range(100):
        try:
            req = urllib.request.Request(url + "/api/ping",
                                        headers={"X-Obscura-Token": API_TOKEN})
            urllib.request.urlopen(req, timeout=0.3); break
        except Exception:
            time.sleep(0.1)

    if "--browser" in sys.argv:
        # DEBUG ONLY. Normal use is the native window below.
        import webbrowser
        webbrowser.open(url + f"/?t={API_TOKEN}")
        print(f"Obscura running at {url} — press Ctrl+C to quit.")
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt:
            server.should_exit = True
    else:
        import scrapers as scraper_engine
        scraper_engine.install_bundled()     # frozen build only: ship the library
        import webview

        window = webview.create_window(
            "Obscura", url + f"/?t={API_TOKEN}", width=1360, height=860,
            min_size=(960, 640), background_color=caption_colors()[0])

        def _paint_caption(*_):
            # Windows paints the title bar itself: pywebview's background_color
            # only covers the page area, so DWM has to be told the colours.
            # DWMWA_CAPTION_COLOR (35) / DWMWA_TEXT_COLOR (36) repaint the bar
            # to match the theme; older Windows builds reject them, in which
            # case at least go dark so the default white bar doesn't glare.
            # Best-effort cosmetic — must never break startup. (Changing the
            # theme in Settings applies at the next launch; repainting live
            # would need a backend bridge.)
            try:
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, "Obscura")
                if not hwnd:
                    return

                def _set(attr, val):
                    v = ctypes.c_uint(val & 0xFFFFFFFF)
                    return ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)) == 0

                bg, fg = caption_colors()
                cb, cf = colorref(bg), colorref(fg)
                if cb is None or cf is None or not (_set(35, cb) and _set(36, cf)):
                    if is_dark(bg):
                        for attr in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE
                            _set(attr, 1)
            except Exception:
                pass

        window.events.shown += _paint_caption
        webview.start()
        server.should_exit = True

if __name__ == "__main__":
    try:
        main()
    except Exception:
        # console=False: without this the user sees a process that does nothing.
        db.alert("Obscura could not start", traceback.format_exc())
        raise
