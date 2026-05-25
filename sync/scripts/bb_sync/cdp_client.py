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

    def _send(self, method: str, params: dict = None) -> dict:
        self._msg_id += 1
        self._ws.send(json.dumps({"id": self._msg_id, "method": method, "params": params or {}}))
        return json.loads(self._ws.recv())

    def fetch_json(self, path: str, params: dict = None) -> dict:
        import requests
        path_js = json.dumps(path)
        params_js = json.dumps(params or {})
        js = (
            f"(async () => {{\n"
            f"  const url = new URL({path_js}, location.origin);\n"
            f"  Object.entries({params_js}).forEach(([k, v]) => url.searchParams.set(k, String(v)));\n"
            f"  const r = await fetch(url.toString(), {{\n"
            f"    credentials: 'include',\n"
            f"    headers: {{Accept: 'application/json'}}\n"
            f"  }});\n"
            f"  return {{status: r.status, body: r.ok ? await r.json() : null}};\n"
            f"}})()"
        )
        result = self._send("Runtime.evaluate", {
            "expression": js,
            "awaitPromise": True,
            "returnByValue": True,
            "timeout": 30000,
        })
        inner = result.get("result", {})
        if "exceptionDetails" in inner:
            desc = inner["exceptionDetails"].get("text", "unknown error")
            raise RuntimeError(f"fetch() failed in browser tab: {desc}")
        value = inner.get("result", {}).get("value", {})
        status = value.get("status", 0)
        if not (200 <= status < 300):
            fake = requests.Response()
            fake.status_code = status
            raise requests.HTTPError(response=fake)
        return value.get("body") or {}

    def get_all_cookies(self) -> dict:
        result = self._send("Network.getAllCookies")
        all_cookies = result.get("result", {}).get("cookies", [])
        return {
            c["name"]: c["value"]
            for c in all_cookies
            if (
                _DOMAIN in c.get("domain", "")
                or c.get("domain", "").lstrip(".") in _DOMAIN
            )
            and not any(c["name"].startswith(p) for p in self._TRACKING_PREFIXES)
        }

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
