# Playwright Blackboard Session — Design Spec

**Date:** 2026-10-05
**Status:** Implemented
**Supersedes:** [2026-05-25-cdp-fetch-proxy-design.md](2026-05-25-cdp-fetch-proxy-design.md)

---

## Problem

`bb_sync` attached to the user's everyday Edge/Chrome over the Chrome DevTools Protocol on port 9222. An audit found:

1. **Security.** Any local process that can reach `127.0.0.1:9222` can call `Network.getAllCookies` and read every site's session (email, banking, …), not just Blackboard's.
2. **Broken on current browsers.** Chromium 136+ ignores `--remote-debugging-port` on the default profile. If the browser is already running (e.g. Edge startup boost), the flag is dropped entirely, so the start-up wizard fails silently.
3. **Cookie leak.** Downloads used `requests` with a cookie dict that had no domain. Blackboard cookies were therefore sent to *any* host, including third-party links embedded in course HTML.
4. **Login detection.** The wizard treated *any* Blackboard-domain cookie as "logged in". Anonymous pre-login cookies passed that check.

Reading cookies from the browser's files instead was rejected. It means defeating Chromium's app-bound cookie encryption (infostealer behaviour), and plain cookie replay is rejected by Blackboard anyway (see the superseded spec).

## Design

The dashboard owns a **dedicated browser profile** (`~/.uni-dashboard/bb-profile`) and drives it with Playwright.

```
Sync page ──POST /api/bb/login──▶ backend ──subprocess──▶ bb_sync --login   (headed window, user signs in)
Sync page ──GET  /api/sync/courses / POST /api/sync/run──▶ bb_sync           (headless, saved session)
```

### `BbSession` (`sync/scripts/bb_sync/bb_session.py`)

- **Launch.** Calls `launch_persistent_context(profile)`, trying browsers in this order:
  1. `BB_BROWSER_PATH`
  2. Brave (if installed)
  3. Edge
  4. Chrome
  5. Bundled Chromium (`playwright install chromium` on demand)
- **Session persistence.** Chromium drops session cookies (Blackboard's `BbRouter`, `JSESSIONID`) on exit. So after every successful auth check the context's cookies are saved to `bb-cookies.json` in the profile, and restored on launch.
- **`ensure_logged_in()` (headless):**
  1. Request `users/me` with the restored session.
  2. If that fails, navigate to Blackboard and wait up to 20s for the Microsoft SSO round-trip to come back.
  3. Give up early once the page sits still on the identity provider, meaning a real login is needed.
- **`interactive_login()` (headed).** Polls every open page for a successful `users/me` until the user finishes signing in, or closes the window.
- **Auth check.** An in-page `fetch('/learn/api/public/v1/users/me')`, falling back to `context.request` (same cookie jar). The fallback was added after the in-page check alone missed a completed login in a headed Brave window.
- **`fetch_json()`.** API calls run as in-page `fetch()`, unchanged from the CDP proxy design, so `BlackboardClient` keeps its interface.
- **`cookie_jar()`.** A `RequestsCookieJar` with each cookie's real domain/path, used for streamed downloads. Cookies are only sent to matching hosts.

### CLI contract (`python -m bb_sync`)

| Flag | Behaviour |
|---|---|
| `--login` | Headed login; prints `{"user": …}`; exit 0, or 3 if not completed |
| `--list-courses` | JSON list incl. `code`, `term_id`, `available` |
| *(none)* / `--modules` | File sync (+ grades unless `--no-grades`) |
| `--grades` | Grades only |

- **Exit code `3`** means "not logged in". The backend maps it to HTTP 401, and the Sync page shows **Connect Blackboard**.
- **Completion marker.** After a file sync, `__synced__:CODE,…` is printed. The backend consumes it, adds those modules to `modules.json` (using names cached from `--list-courses`) and reseeds topics.

### Backend (`backend/app/routes/sync.py`)

- **Serialised access.** The profile can only be open in one process. Login, course listing and sync therefore share one busy flag, and a second request gets `409`.
- **Sync as a task.** Each sync runs as an asyncio task that owns the flag, so it is always released. A closed SSE stream cancels the task and kills the subprocess.
- **Environment.** `Settings.bbsync_env()` passes `BB_LOCAL_ROOT` / `BB_*_PATH` from the backend's own settings, plus `PYTHONUNBUFFERED=1` for live log lines.

## Consequences

- **One-time login.** The user signs in once per profile. Silent SSO usually renews expired Blackboard sessions without any window.
- **No exposed browser.** The user's everyday browser is never touched and no debugging port is opened.
- **Playwright dependency.** It's added to `start.py` and the backend. No browser download is needed when Brave, Edge or Chrome is installed.
