import json
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from config import BB_BASE_URL, COOKIE_CACHE

_CDP_PORTS = [9222, 9223]

_SETUP_HINT = (
    "Open Edge or Chrome with the remote debugging port enabled, then log in to Blackboard:\n"
    "\n"
    "  Windows / WSL2:\n"
    "    msedge.exe --remote-debugging-port=9222\n"
    "    chrome.exe --remote-debugging-port=9222\n"
    "\n"
    "  Linux:\n"
    "    google-chrome --remote-debugging-port=9222\n"
    "    chromium-browser --remote-debugging-port=9222\n"
    "\n"
    "Then navigate to Blackboard, log in, and try again."
)


def _cdp_port() -> int | None:
    """Return the first CDP port that is reachable, or None."""
    for port in _CDP_PORTS:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
            return port
        except Exception:
            continue
    return None


def _extract_via_cdp(domain: str, port: int) -> dict:
    """
    Pull cookies from a running browser via CDP WebSocket.
    Requires websocket-client: pip install websocket-client
    """
    try:
        import websocket as _ws
    except ImportError as exc:
        raise RuntimeError(
            "websocket-client not installed — run: pip install websocket-client"
        ) from exc

    try:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read()
        targets = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Could not list CDP targets on port {port}: {e}") from e

    pages = [t for t in targets if t.get("type") == "page"]
    if pages:
        ws_url = pages[0]["webSocketDebuggerUrl"]
    else:
        try:
            new_raw = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/new", timeout=5
            ).read()
            ws_url = json.loads(new_raw)["webSocketDebuggerUrl"]
        except Exception as e:
            raise RuntimeError(f"No CDP page targets on port {port}: {e}") from e

    ws_url = ws_url.replace("localhost", "127.0.0.1")

    try:
        ws = _ws.WebSocket()
        ws.connect(ws_url, timeout=10, suppress_origin=True)
        ws.settimeout(10)
        ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
        result = json.loads(ws.recv())
        ws.close()
    except Exception as e:
        raise RuntimeError(f"CDP WebSocket call failed: {e}") from e

    _TRACKING_PREFIXES = ("AMCV_", "_ga", "_gid", "_hjid", "s_fid", "s_sq", "s_vi", "s_cc")
    all_domain_cookies = {
        c["name"]: c["value"]
        for c in result.get("result", {}).get("cookies", [])
        if domain in c.get("domain", "") or c.get("domain", "").lstrip(".") in domain
    }
    session_cookies = {
        k: v for k, v in all_domain_cookies.items()
        if not any(k.startswith(p) for p in _TRACKING_PREFIXES)
    }
    if not session_cookies:
        noun = "only tracking cookies" if all_domain_cookies else "no cookies"
        raise RuntimeError(
            f"Found {noun} for {domain} — you are not logged in to Blackboard.\n"
            f"Open {domain} in your browser, log in, then retry."
        )
    return session_cookies


def _save_cache(path: Path, cookies: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies))


def extract_bb_cookies(force_refresh: bool = False) -> dict:
    """
    Return Blackboard session cookies.

    Uses the browser's CDP debug port (Edge or Chrome on 127.0.0.1:9222).
    Caches cookies for 1 hour. Raises RuntimeError if extraction fails.
    """
    cache = Path(COOKIE_CACHE)
    if not force_refresh and cache.exists():
        if time.time() - cache.stat().st_mtime < 3600:
            try:
                return json.loads(cache.read_text())
            except (json.JSONDecodeError, OSError):
                pass

    domain = urlparse(BB_BASE_URL).netloc

    port = _cdp_port()
    if port is None:
        raise RuntimeError(
            f"Could not connect to a browser debug port "
            f"(tried {', '.join(str(p) for p in _CDP_PORTS)}).\n\n"
            + _SETUP_HINT
        )

    print(f"    [cdp] Extracting cookies from browser on port {port}…")
    cookies = _extract_via_cdp(domain, port)
    _save_cache(cache, cookies)
    return cookies
