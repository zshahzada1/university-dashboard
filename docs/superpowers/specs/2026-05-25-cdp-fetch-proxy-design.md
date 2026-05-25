# CDP Fetch Proxy — Design Spec

**Date:** 2026-05-25  
**Status:** Approved  
**Problem:** Blackboard REST API returns 401 when Python `requests` replays cookies extracted via CDP. Root cause is missing CSRF/session headers that the browser manages automatically.

---

## Goal

Replace cookie-extraction-and-replay with in-browser `fetch()` calls evaluated via CDP `Runtime.evaluate`. The browser tab already holds a valid authenticated session; we delegate all JSON API calls to it and eliminate the entire class of "wrong headers" failures. Binary file downloads continue to use `requests` with a one-time cookie snapshot.

---

## Scope

**In scope:**
- New `CdpSession` class in `cdp_client.py`
- Modified `BlackboardClient` constructor and `_get()` method
- Deletion of `cookie_extractor.py`
- Updated entry point in `__main__.py`

**Out of scope:** `syncer.py`, `grades.py`, `sync.py` (FastAPI route), `config.py` — all unchanged.

---

## Architecture

### High-level flow

```
Before:
  CDP → extract cookies → close WebSocket → Python requests (replay cookies)

After:
  CDP WebSocket (open for full sync session)
    ├── JSON API calls → Runtime.evaluate fetch() in Blackboard tab → dict
    └── File downloads → Network.getAllCookies (once) → requests.Session (streaming)
```

### `CdpSession` (`cdp_client.py`)

Replaces `cookie_extractor.py`. Owns the CDP WebSocket for the lifetime of a sync.

**Constructor:** Scans `_CDP_PORTS` (9222, 9223) for a reachable port, then selects the first CDP target whose URL contains the Blackboard domain. Raises `RuntimeError` with a clear "open Blackboard in Edge" message if no matching tab is found.

**`fetch_json(path, params=None) -> dict`**

Evaluates this JS in the browser tab via `Runtime.evaluate` with `awaitPromise=True`, `returnByValue=True`:

```js
(async () => {
  const url = new URL('/learn/api/...', location.origin);
  // params appended via url.searchParams
  const r = await fetch(url, {
    credentials: 'include',
    headers: {Accept: 'application/json'}
  });
  return {status: r.status, body: r.ok ? await r.json() : null};
})()
```

Returns the `body` dict. Raises `requests.HTTPError` (constructed with a fake `requests.Response` carrying the status code) on non-2xx — so all existing `except requests.HTTPError` branches in `bb_client.py` continue to work without change.

**`get_all_cookies() -> dict[str, str]`**

Calls `Network.getAllCookies` once. Filters to Blackboard domain cookies, strips tracking prefixes. Used only at `BlackboardClient.__init__` time to seed the download session.

**Context manager:** `__enter__`/`__exit__` open and close the WebSocket, so callers use `with CdpSession() as cdp:`.

---

### `BlackboardClient` (`bb_client.py`)

```python
# Before
class BlackboardClient:
    def __init__(self, cookies: dict): ...

# After
class BlackboardClient:
    def __init__(self, cdp: CdpSession): ...
```

- `_get(path, params)` → `self._cdp.fetch_json(path, params)`
- `download_stream(url)` → unchanged; uses `self._session` (a `requests.Session` seeded with cookies from `cdp.get_all_cookies()` at init time)
- All other methods (`get_current_user`, `get_courses`, `get_contents`, etc.) unchanged

---

### Entry point (`__main__.py`)

```python
# Before
cookies = extract_bb_cookies(force_refresh=args.refresh_cookies)
client = BlackboardClient(cookies)

# After
with CdpSession() as cdp:
    client = BlackboardClient(cdp)
    # ... rest of sync unchanged
```

`--refresh-cookies` flag becomes a no-op (no cache to refresh). Keep it accepted by the argument parser and silently ignore it — the flag appears in documented sync commands in CLAUDE.md so removing it would break existing usage.

---

## Error handling

| Condition | Behaviour |
|-----------|-----------|
| No CDP port reachable | RuntimeError: "Open Edge with --remote-debugging-port=9222" |
| No Blackboard tab found | RuntimeError: "Open studentcentral.brighton.ac.uk in Edge and log in" |
| fetch() returns non-2xx | `requests.HTTPError` with fake response (status code set) |
| WebSocket drops mid-sync | RuntimeError surfaces naturally; sync fails with a clear message |

---

## Files changed

| File | Change |
|------|--------|
| `bb_sync/cdp_client.py` | New — `CdpSession` class |
| `bb_sync/cookie_extractor.py` | Deleted |
| `bb_sync/bb_client.py` | Constructor + `_get()` + init-time cookie snapshot for downloads |
| `bb_sync/__main__.py` | Entry point wiring |
| `bb_sync/test_cookie_extractor.py` | Deleted |
| `bb_sync/test_cdp_client.py` | New — unit tests for `CdpSession` with mocked WebSocket |

---

## What stays the same

- `syncer.py`, `grades.py` — no changes
- `sync.py` FastAPI route — no changes
- `config.py` — no changes
- Cookie cache path (`~/.cache/bb_sync/cookies.json`) — no longer written (cache concept eliminated)
- All `requests.HTTPError` handling in `bb_client.py` — compatible via fake response object
