"""Obscura entry point — starts the API server, then opens a native window.
Run `python main.py --browser` to use your normal browser instead."""
import sys, os, time, socket, threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from server import app, API_TOKEN

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
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
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
        import webbrowser
        webbrowser.open(url + f"/?t={API_TOKEN}")
        print(f"Obscura running at {url} — press Ctrl+C to quit.")
        try:
            while True: time.sleep(3600)
        except KeyboardInterrupt:
            server.should_exit = True
    else:
        import webview
        webview.create_window("Obscura", url + f"/?t={API_TOKEN}", width=1360, height=860, min_size=(960, 640))
        webview.start()
        server.should_exit = True

if __name__ == "__main__":
    main()
