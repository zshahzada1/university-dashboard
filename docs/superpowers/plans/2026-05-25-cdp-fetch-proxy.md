# CDP Fetch Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace cookie-extraction-and-replay in the Blackboard sync with in-browser `fetch()` calls evaluated via CDP `Runtime.evaluate`, eliminating 401 auth failures caused by missing CSRF/session headers.

**Architecture:** A new `CdpSession` class holds a persistent CDP WebSocket to an open Blackboard tab in Edge. All JSON API calls go through `fetch()` evaluated in that tab (browser handles auth). File downloads keep a `requests.Session` seeded once with cookies from `Network.getAllCookies`. `BlackboardClient` now takes a `CdpSession` instead of a `cookies` dict.

**Tech Stack:** Python 3.12, `websocket-client`, `requests`, CDP (Chrome DevTools Protocol), `unittest.mock`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `sync/scripts/bb_sync/cdp_client.py` | **Create** | `CdpSession` — CDP WebSocket, `fetch_json()`, `get_all_cookies()`, context manager |
| `sync/scripts/bb_sync/test_cdp_client.py` | **Create** | Unit tests for `CdpSession` |
| `sync/scripts/bb_sync/bb_client.py` | **Modify** | Constructor takes `CdpSession`; `_get()` delegates to `fetch_json()` |
| `sync/scripts/bb_sync/test_bb_client.py` | **Modify** | Update `_make_client()` and 5 tests that mock `_session.get` |
| `sync/scripts/bb_sync/__main__.py` | **Modify** | Entry point: `with CdpSession() as cdp: BlackboardClient(cdp)` |
| `sync/scripts/bb_sync/cookie_extractor.py` | **Delete** | Replaced by `CdpSession` |
| `sync/scripts/bb_sync/test_cookie_extractor.py` | **Delete** | Replaced by `test_cdp_client.py` |

All test commands run from `sync/scripts/` using the existing venv: `cd sync/scripts && .venv/bin/python -m pytest`.

---

## Task 1: Create `CdpSession` — port detection, tab selection, WebSocket connection

**Files:**
- Create: `sync/scripts/bb_sync/cdp_client.py`
- Create: `sync/scripts/bb_sync/test_cdp_client.py`

- [ ] **Step 1: Write failing tests**

```python
# sync/scripts/bb_sync/test_cdp_client.py
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

BB_WS_URL = "ws://127.0.0.1:9222/page/1"
BB_PAGE_URL = "https://studentcentral.brighton.ac.uk/webapps/portal"
OTHER_URL = "https://google.com"


def _version_mock():
    m = MagicMock()
    m.read.return_value = b"{}"
    return m


def _targets_mock(targets):
    m = MagicMock()
    m.read.return_value = json.dumps(targets).encode()
    return m


def _bb_target(ws=BB_WS_URL):
    return {"type": "page", "url": BB_PAGE_URL, "webSocketDebuggerUrl": ws}


def _other_target():
    return {"type": "page", "url": OTHER_URL, "webSocketDebuggerUrl": "ws://127.0.0.1:9222/page/2"}


class TestCdpSessionInit(unittest.TestCase):
    def test_raises_when_no_port_reachable(self):
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            with self.assertRaises(RuntimeError) as ctx:
                from cdp_client import CdpSession
                CdpSession()
        self.assertIn("9222", str(ctx.exception))

    def test_raises_when_no_blackboard_tab(self):
        ws = MagicMock()
        with patch("urllib.request.urlopen", side_effect=[
            _version_mock(),
            _targets_mock([_other_target()])
        ]), patch("websocket.WebSocket", return_value=ws):
            with self.assertRaises(RuntimeError) as ctx:
                from cdp_client import CdpSession
                CdpSession()
        self.assertIn("studentcentral.brighton.ac.uk", str(ctx.exception))

    def test_connects_to_blackboard_tab(self):
        ws = MagicMock()
        with patch("urllib.request.urlopen", side_effect=[
            _version_mock(),
            _targets_mock([_bb_target()])
        ]), patch("websocket.WebSocket", return_value=ws):
            from cdp_client import CdpSession
            CdpSession()
        ws.connect.assert_called_once_with(BB_WS_URL, timeout=10, suppress_origin=True)

    def test_prefers_blackboard_tab_over_others(self):
        bb_ws = "ws://127.0.0.1:9222/page/2"
        ws = MagicMock()
        with patch("urllib.request.urlopen", side_effect=[
            _version_mock(),
            _targets_mock([_other_target(), _bb_target(ws=bb_ws)])
        ]), patch("websocket.WebSocket", return_value=ws):
            from cdp_client import CdpSession
            CdpSession()
        ws.connect.assert_called_once_with(bb_ws, timeout=10, suppress_origin=True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/test_cdp_client.py::TestCdpSessionInit -v
```

Expected: `ModuleNotFoundError: No module named 'cdp_client'`

- [ ] **Step 3: Create `cdp_client.py` with port detection and tab selection**

```python
# sync/scripts/bb_sync/cdp_client.py
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
            except Exception:
                continue
        return None

    def _find_bb_tab(self, port: int) -> str:
        raw = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read()
        targets = json.loads(raw)
        pages = [t for t in targets if t.get("type") == "page"]
        bb_pages = [p for p in pages if _DOMAIN in p.get("url", "")]
        if not bb_pages:
            raise RuntimeError(
                f"No Blackboard tab found in Edge.\n"
                f"Open {BB_BASE_URL} in Edge and log in, then retry.\n\n{_SETUP_HINT}"
            )
        ws_url = bb_pages[0]["webSocketDebuggerUrl"]
        return ws_url.replace("localhost", "127.0.0.1")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/test_cdp_client.py::TestCdpSessionInit -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd sync/scripts/bb_sync && git add cdp_client.py test_cdp_client.py
git commit -m "feat: add CdpSession with port detection and Blackboard tab selection"
```

---

## Task 2: Add `_send()` and `fetch_json()` to `CdpSession`

`fetch_json()` evaluates a `fetch()` call inside the live Blackboard tab and returns the parsed JSON body. It raises `requests.HTTPError` (with the HTTP status code) on non-2xx so existing error-handling branches in `bb_client.py` work unchanged.

**Files:**
- Modify: `sync/scripts/bb_sync/cdp_client.py`
- Modify: `sync/scripts/bb_sync/test_cdp_client.py`

- [ ] **Step 1: Append `TestCdpSessionFetchJson` to `test_cdp_client.py`**

Add this class at the end of `test_cdp_client.py`, before `if __name__ == "__main__":`:

```python
class TestCdpSessionFetchJson(unittest.TestCase):
    def _make_session(self):
        """Bypass __init__ to get a CdpSession with a mock WebSocket."""
        from cdp_client import CdpSession
        s = object.__new__(CdpSession)
        s._ws = MagicMock()
        s._msg_id = 0
        return s

    def _eval_response(self, status, body=None):
        return json.dumps({
            "id": 1,
            "result": {"result": {"type": "object", "value": {"status": status, "body": body}}}
        })

    def _eval_error(self, text="NetworkError"):
        return json.dumps({
            "id": 1,
            "result": {
                "result": {"type": "object", "subtype": "error", "description": text},
                "exceptionDetails": {"text": text},
            }
        })

    def test_returns_body_on_200(self):
        s = self._make_session()
        s._ws.recv.return_value = self._eval_response(200, {"id": "u1"})
        result = s.fetch_json("/learn/api/public/v1/users/me")
        self.assertEqual(result["id"], "u1")

    def test_raises_http_error_on_401(self):
        import requests
        s = self._make_session()
        s._ws.recv.return_value = self._eval_response(401)
        with self.assertRaises(requests.HTTPError) as ctx:
            s.fetch_json("/learn/api/public/v1/users/me")
        self.assertEqual(ctx.exception.response.status_code, 401)

    def test_raises_http_error_on_404(self):
        import requests
        s = self._make_session()
        s._ws.recv.return_value = self._eval_response(404)
        with self.assertRaises(requests.HTTPError) as ctx:
            s.fetch_json("/some/path")
        self.assertEqual(ctx.exception.response.status_code, 404)

    def test_raises_runtime_error_on_js_exception(self):
        s = self._make_session()
        s._ws.recv.return_value = self._eval_error("NetworkError: failed to fetch")
        with self.assertRaises(RuntimeError) as ctx:
            s.fetch_json("/learn/api/public/v1/users/me")
        self.assertIn("NetworkError", str(ctx.exception))

    def test_sends_params_embedded_in_js(self):
        s = self._make_session()
        s._ws.recv.return_value = self._eval_response(200, {"results": []})
        s.fetch_json("/learn/api/public/v1/users/me/courses", {"limit": 200, "expand": "course"})
        sent = json.loads(s._ws.send.call_args[0][0])
        self.assertEqual(sent["method"], "Runtime.evaluate")
        self.assertIn("limit", sent["params"]["expression"])
        self.assertIn("200", sent["params"]["expression"])
        self.assertTrue(sent["params"]["awaitPromise"])
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/test_cdp_client.py::TestCdpSessionFetchJson -v
```

Expected: `AttributeError: 'CdpSession' object has no attribute 'fetch_json'`

- [ ] **Step 3: Add `_send()` and `fetch_json()` to `cdp_client.py`**

Add these two methods inside the `CdpSession` class, after `_find_bb_tab`:

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/test_cdp_client.py::TestCdpSessionFetchJson -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sync/scripts/bb_sync/cdp_client.py sync/scripts/bb_sync/test_cdp_client.py
git commit -m "feat: add CdpSession._send() and fetch_json() via Runtime.evaluate"
```

---

## Task 3: Add `get_all_cookies()` and context manager to `CdpSession`

**Files:**
- Modify: `sync/scripts/bb_sync/cdp_client.py`
- Modify: `sync/scripts/bb_sync/test_cdp_client.py`

- [ ] **Step 1: Append `TestCdpSessionCookiesAndLifecycle` to `test_cdp_client.py`**

Add after `TestCdpSessionFetchJson`, before `if __name__ == "__main__":`:

```python
class TestCdpSessionCookiesAndLifecycle(unittest.TestCase):
    def _make_session(self):
        from cdp_client import CdpSession
        s = object.__new__(CdpSession)
        s._ws = MagicMock()
        s._msg_id = 0
        return s

    def _cookies_response(self, cookies):
        return json.dumps({"id": 1, "result": {"cookies": cookies}})

    def test_returns_bb_domain_cookies(self):
        s = self._make_session()
        s._ws.recv.return_value = self._cookies_response([
            {"name": "BbRouter", "value": "abc", "domain": ".brighton.ac.uk"},
            {"name": "_ga", "value": "x", "domain": ".brighton.ac.uk"},
            {"name": "other", "value": "y", "domain": ".example.com"},
        ])
        result = s.get_all_cookies()
        self.assertIn("BbRouter", result)
        self.assertEqual(result["BbRouter"], "abc")
        self.assertNotIn("_ga", result)    # stripped: tracking prefix
        self.assertNotIn("other", result)  # stripped: wrong domain

    def test_context_manager_closes_ws(self):
        s = self._make_session()
        with s:
            pass
        s._ws.close.assert_called_once()

    def test_close_is_safe_when_ws_already_closed(self):
        s = self._make_session()
        s._ws.close.side_effect = Exception("already closed")
        s.close()  # must not raise
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/test_cdp_client.py::TestCdpSessionCookiesAndLifecycle -v
```

Expected: `AttributeError: 'CdpSession' object has no attribute 'get_all_cookies'`

- [ ] **Step 3: Add `get_all_cookies()`, `close()`, and context manager to `cdp_client.py`**

Add these methods inside `CdpSession`, after `fetch_json`:

```python
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
```

- [ ] **Step 4: Run all `test_cdp_client.py` tests**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/test_cdp_client.py -v
```

Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sync/scripts/bb_sync/cdp_client.py sync/scripts/bb_sync/test_cdp_client.py
git commit -m "feat: add CdpSession.get_all_cookies() and context manager"
```

---

## Task 4: Update `BlackboardClient` to accept `CdpSession`

`_get()` now delegates to `cdp.fetch_json()`. The `requests.Session` on `self._session` is seeded once from `cdp.get_all_cookies()` and used only by `download_stream()`. All other methods on `BlackboardClient` are unchanged.

**Files:**
- Modify: `sync/scripts/bb_sync/bb_client.py`
- Modify: `sync/scripts/bb_sync/test_bb_client.py`

- [ ] **Step 1: Write new constructor and `_get()` tests in `test_bb_client.py`**

Add this class **before** the existing `TestBlackboardClient` class:

```python
class TestBlackboardClientWithCdp(unittest.TestCase):
    def _make_cdp(self, fetch_return=None, cookies=None):
        cdp = MagicMock()
        cdp.fetch_json.return_value = fetch_return or {}
        cdp.get_all_cookies.return_value = cookies or {"BbRouter": "fake"}
        return cdp

    def test_constructor_seeds_session_from_cdp_cookies(self):
        cdp = self._make_cdp(cookies={"BbRouter": "abc123"})
        client = BlackboardClient(cdp)
        self.assertEqual(client._session.cookies.get("BbRouter"), "abc123")

    def test_get_delegates_to_fetch_json(self):
        cdp = self._make_cdp(fetch_return={"id": "u1"})
        client = BlackboardClient(cdp)
        result = client._get("/learn/api/public/v1/users/me")
        cdp.fetch_json.assert_called_once_with("/learn/api/public/v1/users/me", None)
        self.assertEqual(result["id"], "u1")

    def test_get_passes_params_to_fetch_json(self):
        cdp = self._make_cdp(fetch_return={"results": []})
        client = BlackboardClient(cdp)
        client._get("/learn/api/public/v1/courses", {"limit": 200})
        cdp.fetch_json.assert_called_once_with("/learn/api/public/v1/courses", {"limit": 200})
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/test_bb_client.py::TestBlackboardClientWithCdp -v
```

Expected: `TypeError` — old constructor expects `cookies: dict`.

- [ ] **Step 3: Replace `__init__` and `_get` in `bb_client.py`**

In `bb_client.py`, replace lines 11–22 (the `__init__` and `_get` methods) with:

```python
    def __init__(self, cdp):
        self._cdp = cdp
        self._base = BB_BASE_URL.rstrip("/")
        self._session = requests.Session()
        self._session.cookies.update(cdp.get_all_cookies())

    def _get(self, path: str, params: dict = None) -> dict:
        return self._cdp.fetch_json(path, params)
```

Remove the old lines: `self._cookies = cookies` and the old `_get` body that called `self._session.get(...)`.

- [ ] **Step 4: Update `_make_client()` in `test_bb_client.py` — both occurrences**

In `TestBlackboardClient._make_client` and `TestBlackboardClientGradebook._make_client`, replace:

```python
    def _make_client(self):
        return BlackboardClient({"BbRouter": "fake", "JSESSIONID": "fake"})
```

with:

```python
    def _make_client(self):
        cdp = MagicMock()
        cdp.get_all_cookies.return_value = {"BbRouter": "fake", "JSESSIONID": "fake"}
        return BlackboardClient(cdp)
```

- [ ] **Step 5: Update the 5 tests that mock `_session.get` — replace with `_cdp.fetch_json`**

In `TestBlackboardClient`, replace these 5 test methods:

```python
    def test_get_current_user(self):
        client = self._make_client()
        client._cdp.fetch_json.return_value = MOCK_ME
        user = client.get_current_user()
        self.assertEqual(user["id"], "_123_1")

    def test_get_courses(self):
        client = self._make_client()
        client._cdp.fetch_json.return_value = MOCK_COURSES
        courses = client.get_courses("_123_1")
        self.assertEqual(len(courses), 2)
        self.assertEqual(courses[0]["courseId"], "FN585")

    def test_get_contents(self):
        client = self._make_client()
        client._cdp.fetch_json.return_value = MOCK_CONTENTS
        contents = client.get_contents("_1_1")
        self.assertEqual(len(contents), 2)

    def test_get_attachments(self):
        client = self._make_client()
        client._cdp.fetch_json.return_value = MOCK_ATTACHMENTS
        attachments = client.get_attachments("_1_1", "_10_1")
        self.assertEqual(attachments[0]["fileName"], "week1.pdf")

    def test_get_courses_filters_null_availability(self):
        mock_data = {"results": [
            {"courseId": "FN585", "availability": None,
             "course": {"id": "_1_1", "courseId": "FN585", "name": "FN585"}},
            {"courseId": "FA565", "availability": {"available": "Yes"},
             "course": {"id": "_2_1", "courseId": "FA565", "name": "FA565"}},
        ]}
        client = self._make_client()
        client._cdp.fetch_json.return_value = mock_data
        courses = client.get_courses("_123_1")
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["courseId"], "FA565")
```

- [ ] **Step 6: Run all `bb_client` tests**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/test_bb_client.py -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add sync/scripts/bb_sync/bb_client.py sync/scripts/bb_sync/test_bb_client.py
git commit -m "feat: update BlackboardClient to use CdpSession instead of cookies dict"
```

---

## Task 5: Wire `__main__.py` to use `CdpSession`

**Files:**
- Modify: `sync/scripts/bb_sync/__main__.py`

- [ ] **Step 1: Update import at the top of `__main__.py`**

Replace:
```python
from cookie_extractor import extract_bb_cookies
```
With:
```python
from cdp_client import CdpSession
```

- [ ] **Step 2: Replace cookie extraction block (lines 43–51)**

Replace:
```python
    print("Extracting Edge cookies from Windows…", file=out)
    try:
        cookies = extract_bb_cookies(force_refresh=args.refresh_cookies)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=out)
        sys.exit(1)

    client = BlackboardClient(cookies)
    syncer = Syncer(client, LOCAL_ROOT)
```

With:
```python
    print("Connecting to Blackboard tab in Edge…", file=out)
    try:
        cdp = CdpSession()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=out)
        sys.exit(1)

    client = BlackboardClient(cdp)
    syncer = Syncer(client, LOCAL_ROOT)
```

- [ ] **Step 3: Update `--refresh-cookies` help text and auth error hint**

Change the `--refresh-cookies` help text (around line 29):
```python
    parser.add_argument("--refresh-cookies", action="store_true",
                        help="(no-op) Kept for CLI compatibility")
```

Change the auth error hint (around line 58):
```python
        print("Make sure Edge has a Blackboard tab open and you are logged in.", file=out)
```

- [ ] **Step 4: Smoke test (requires Edge open with a Blackboard tab)**

```bash
cd sync/scripts && .venv/bin/python -m bb_sync --list-courses
```

Expected output:
```
Blackboard Sync — https://studentcentral.brighton.ac.uk
Connecting to Blackboard tab in Edge…
Checking authentication…
Logged in as: <username>
Fetching enrolled courses…
[JSON list to stdout]
```

- [ ] **Step 5: Commit**

```bash
git add sync/scripts/bb_sync/__main__.py
git commit -m "feat: wire CdpSession into __main__ entry point; --refresh-cookies is now a no-op"
```

---

## Task 6: Delete `cookie_extractor.py` and `test_cookie_extractor.py`

**Files:**
- Delete: `sync/scripts/bb_sync/cookie_extractor.py`
- Delete: `sync/scripts/bb_sync/test_cookie_extractor.py`

- [ ] **Step 1: Delete the files**

```bash
rm sync/scripts/bb_sync/cookie_extractor.py sync/scripts/bb_sync/test_cookie_extractor.py
```

- [ ] **Step 2: Run the full test suite to confirm no imports remain**

```bash
cd sync/scripts && .venv/bin/python -m pytest bb_sync/ -v
```

Expected: All tests PASS — no `ModuleNotFoundError: No module named 'cookie_extractor'`.

- [ ] **Step 3: Commit**

```bash
git add -u sync/scripts/bb_sync/cookie_extractor.py sync/scripts/bb_sync/test_cookie_extractor.py
git commit -m "chore: delete cookie_extractor — superseded by CdpSession"
```
