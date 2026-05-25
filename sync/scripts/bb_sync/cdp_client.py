import json
import urllib.request
from urllib.parse import urlparse

from config import BB_BASE_URL

_CDP_PORTS = [9222, 9223]
_DOMAIN = urlparse(BB_BASE_URL).netloc

_SETUP_HINT = (
    f"  1. Open Edge with --remote-debugging-port=9222\n"
    f"  2. Navigate to {BB_BASE_URL} and log in\n"
    f"  3. Retry"
)


class CdpSession:
    _TRACKING_PREFIXES = ("AMCV_", "_ga", "_gid", "_hjid", "s_fid", "s_sq", "s_vi", "s_cc")

    def __init__(self):
        try:
            import websocket as _ws
        except ImportError as exc:
            raise RuntimeError(
                "websocket-client not installed — run: pip install websocket-client"
            ) from exc

        port = self._find_port()
        if port is None:
            raise RuntimeError(
                f"Could not connect to browser debug port "
                f"(tried {', '.join(str(p) for p in _CDP_PORTS)}).\n\n{_SETUP_HINT}"
            )

        ws_url = self._find_bb_tab(port)
        self._ws = _ws.WebSocket()
        self._ws.connect(ws_url, timeout=10, suppress_origin=True)
        self._ws.settimeout(30)
        self._msg_id = 0

    def _find_port(self) -> int | None:
        for port in _CDP_PORTS:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
                return port
            except OSError:
                continue
        return None

    def _find_bb_tab(self, port: int) -> str:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read()
        targets = json.loads(raw)
        pages = [t for t in targets if t.get("type") == "page"]
        bb_pages = [
            p for p in pages
            if _DOMAIN in p.get("url", "") and "webSocketDebuggerUrl" in p
        ]
        if not bb_pages:
            raise RuntimeError(
                f"No ready Blackboard tab found in Edge.\n"
                f"Open {BB_BASE_URL} in Edge, log in, and wait for the page to finish loading, then retry.\n\n{_SETUP_HINT}"
            )
        ws_url = bb_pages[0]["webSocketDebuggerUrl"]
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(ws_url)
        if parsed.hostname == "localhost":
            ws_url = urlunparse(parsed._replace(netloc=parsed.netloc.replace("localhost", "127.0.0.1", 1)))
        return ws_url
