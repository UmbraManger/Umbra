"""Umbra entry point — starts the API server, then opens a native window.

The HTTP server is the transport pywebview renders (http://127.0.0.1:<port>); it
is not a "browser mode". To debug the UI in your own browser instead, run:

    python main.py --browser   # DEBUG ONLY — opens your default browser
"""
import sys, os, time, socket, threading, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from server import app, API_TOKEN, APP_VERSION
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


class _WinControls:
    """Title-bar buttons for the frameless window — there is no OS chrome.

    State is stored under PRIVATE names on purpose: pywebview walks the js_api
    object with dir()/getattr() and recurses into any public object, so a
    public `window` attribute would publish the whole Window (evaluate_js,
    destroy, ...) into the page. Names starting with '_' are skipped.

    ponytail: `maximized` is tracked here rather than read back from the OS, so
    maximizing with Win+Up desyncs the button glyph (the toggle still works).
    Reading the real state means hooking the form's WndProc, which is far more
    machinery than a title bar is worth.
    """
    _window = None
    _maximized = False

    def minimize(self):
        if self._window:
            self._window.minimize()

    def toggle_max(self):
        if not self._window:
            return
        if self._maximized:
            self._window.restore()
            self._maximized = False
        else:
            self._window.maximize()
            self._maximized = True

    def resize_to(self, width, height):
        """Bottom-right grip: a frameless window has no border to drag."""
        if self._window:
            self._window.resize(max(960, int(width)), max(640, int(height)))

    def close(self):
        if self._window:
            self._window.destroy()

def main():
    # Re-arm the app lock from the stored settings BEFORE serving anything,
    # so a password set in the last session locks this start too.
    _apply_startup_lock()
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
                                        headers={"X-Umbra-Token": API_TOKEN})
            urllib.request.urlopen(req, timeout=0.3); break
        except Exception:
            time.sleep(0.1)

    if "--browser" in sys.argv:
        # DEBUG ONLY. Normal use is the native window below.
        import webbrowser
        webbrowser.open(url + f"/?t={API_TOKEN}")
        print(f"Umbra running at {url} — press Ctrl+C to quit.")
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt:
            server.should_exit = True
    else:
        import scrapers as scraper_engine
        scraper_engine.install_bundled()     # frozen build only: ship the library
        import webview

        controls = _WinControls()
        # frameless: Windows draws no title bar, so the page draws it (see
        # mountTitleBar). easy_drag stays off — it would make every mousedown
        # in the app drag the window; dragging comes from .pywebview-drag-region.
        window = webview.create_window(
            f"Umbra {APP_VERSION}", url + f"/?t={API_TOKEN}", width=1360, height=860,
            min_size=(960, 640), frameless=True, easy_drag=False,
            js_api=controls, background_color=caption_colors()[0])
        controls._window = window
        webview.start()
        server.should_exit = True

if __name__ == "__main__":
    try:
        main()
    except Exception:
        # console=False: without this the user sees a process that does nothing.
        db.alert("Umbra could not start", traceback.format_exc())
        raise
