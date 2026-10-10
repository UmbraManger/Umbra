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

        def _caption_colors():
            """(caption bg, caption text) for the current theme, as '#rrggbb'."""
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

        window = webview.create_window(
            "Obscura", url + f"/?t={API_TOKEN}", width=1360, height=860,
            min_size=(960, 640), background_color=_caption_colors()[0])

        def _paint_caption(*_):
            # Windows paints the title bar itself: pywebview's background_color
            # only covers the page area, so DWM has to be told the colours.
            # DWMWA_CAPTION_COLOR (35) and DWMWA_TEXT_COLOR (36) repaint the
            # bar to match the theme — the earlier DWMWA_USE_IMMERSIVE_DARK_MODE
            # approach only ever made it black with white text, which is why it
            # never matched the app. Best-effort cosmetic, must never break
            # startup. (Changing the theme in Settings doesn't repaint it; no
            # backend bridge exists for that yet, so it applies next launch.)
            try:
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, "Obscura")
                if not hwnd:
                    return

                def _set(attr, val):
                    v = ctypes.c_uint(val)
                    return ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, ctypes.c_int(attr), ctypes.byref(v),
                        ctypes.sizeof(v)) == 0

                def _ref(h):                       # COLORREF is 0x00BBGGRR
                    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
                    return (b << 16) | (g << 8) | r

                bg, fg = _caption_colors()
                if not (_set(35, _ref(bg)) and _set(36, _ref(fg))):
                    # Older Windows rejects 35/36 — at least make the bar dark
                    # so the light app text stays readable.
                    if bg == "#100e0a":
                        for attr in (20, 19):       # DWMWA_USE_IMMERSIVE_DARK_MODE
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
