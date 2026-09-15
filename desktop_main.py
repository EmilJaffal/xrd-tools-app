"""Desktop entrypoint: runs the merged Dash app in a background thread and
opens it in a native OS window via pywebview (WKWebView on macOS, WebView2 on
Windows) instead of a browser tab.

Plain `python desktop_main.py` also works for local testing without any
packaging step.
"""
import socket
import threading
import time
import urllib.error
import urllib.request

import webview

from app_factory import create_app

# First run after a fresh install/build, matplotlib (pulled in transitively via
# pymatgen) has to build its font cache from scratch, which can take well over
# 10s. If the webview window loads the URL before the server is actually up,
# it shows a blank page and never retries — so we wait for a real HTTP
# response before creating the window at all.
STARTUP_TIMEOUT_SECONDS = 60


def _free_port() -> int:
    """Ask the OS for an unused local port instead of hardcoding one, so the
    desktop app never collides with anything else already listening (e.g. a
    developer's own `python app_factory.py` running on 8050)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_ready(url: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(0.3)
    return False


def main():
    app = create_app()
    server = app.server
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    def run_server():
        # use_reloader must stay off: the reloader forks/execs a second
        # process, which doesn't make sense once this is frozen by PyInstaller.
        server.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    ready = _wait_until_ready(url, STARTUP_TIMEOUT_SECONDS)
    window = webview.create_window(
        "XRD Tools",
        url if ready else None,
        html=None if ready else (
            "<h2 style='font-family: sans-serif; margin: 40px;'>"
            "XRD Tools is still starting up (first launch can take a little "
            "longer)&hellip;</h2>"
        ),
        width=1400,
        height=1000,
    )
    if not ready:
        # Keep polling in the background and swap the placeholder for the
        # real app the moment the server responds, instead of leaving the
        # user stuck on a blank/placeholder screen forever.
        def load_when_ready():
            if _wait_until_ready(url, timeout=600):
                window.load_url(url)
        threading.Thread(target=load_when_ready, daemon=True).start()

    webview.start()


if __name__ == "__main__":
    main()
