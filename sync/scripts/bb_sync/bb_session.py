"""Blackboard session backed by a dedicated Playwright browser profile.

The dashboard owns this profile (default ~/.uni-dashboard/bb-profile): the user
logs in once in a visible window (``--login``), and later syncs reuse the saved
session headlessly. The user's everyday browser is never touched and no
debugging port is exposed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from config import BB_BASE_URL, BROWSER_PATH, PROFILE_DIR

ME_PATH = "/learn/api/public/v1/users/me"

# Session cookies (no expiry) are dropped when Chromium exits, so the whole jar
# is saved next to the profile after each successful auth check and restored on launch.
_COOKIE_FILE = "bb-cookies.json"

# JSON API calls run as fetch() inside a Blackboard page so the browser supplies
# whatever session/XSRF state Blackboard expects (plain cookie replay gets 401).
_FETCH_JS = """async ({path, params}) => {
  const url = new URL(path, location.origin);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v));
  const r = await fetch(url.toString(), {credentials: 'include', headers: {Accept: 'application/json'}});
  let body = null;
  if (r.ok) { try { body = await r.json(); } catch (e) { body = null; } }
  return {status: r.status, body};
}"""


def sharepoint_candidates(url: str) -> list[str]:
    """Direct file URLs to try for a SharePoint link, most likely first.

    Sharing links look like ``/:w:/r/sites/…/FN668.docx?d=…``; the ``/:w:/r`` prefix and
    query are dropped to get the file path. If the extension is a document type, the
    same name with the other common extension (.pdf/.docx) is tried next.
    """
    p = urlparse(url)
    path = re.sub(r"^/:[a-z]:/[a-z]/", "/", p.path)
    direct = f"{p.scheme}://{p.netloc}{path}"
    root, ext = os.path.splitext(direct)
    alternates = [root + e for e in (".pdf", ".docx") if ext.lower() in (".pdf", ".docx", ".doc") and e != ext.lower()]
    return [direct, *alternates]


class BbSession:
    def __init__(self, headless: bool = True, profile_dir: str = PROFILE_DIR,
                 base_url: str = BB_BASE_URL):
        self._headless = headless
        self._profile_dir = Path(profile_dir)
        self._base = base_url.rstrip("/")
        self.host = urlparse(self._base).hostname
        self._pw = None
        self._context = None
        self._page = None
        self._sso_hosts: set[str] = set()  # SharePoint sites already signed in this run

    # ── lifecycle ────────────────────────────────────────────────────────────
    def __enter__(self):
        if self._context is None:
            self.open()
        return self

    def __exit__(self, *_):
        self.close()

    def open(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("playwright not installed — start the dashboard with: uv run start.py") from exc
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._context = self._launch()
        self._restore_cookies()
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

    def close(self) -> None:
        for closer in (getattr(self._context, "close", None), getattr(self._pw, "stop", None)):
            if closer:
                try:
                    closer()
                except Exception:
                    pass
        self._context = self._pw = self._page = None

    def _launch(self):
        # Configured browser (Brave by default) first, then installed Edge/Chrome
        # (no download needed), then Playwright's bundled Chromium.
        candidates = [{"executable_path": BROWSER_PATH}] if BROWSER_PATH else []
        candidates += [{"channel": "msedge"}, {"channel": "chrome"}, {}]
        errors = []
        for opts in candidates:
            try:
                return self._pw.chromium.launch_persistent_context(
                    str(self._profile_dir), headless=self._headless,
                    viewport=None if not self._headless else {"width": 1280, "height": 800},
                    **opts,
                )
            except Exception as e:
                label = next(iter(opts.values()), "chromium")
                errors.append(f"{label}: {str(e).splitlines()[0]}")
        # No system browser and no bundled Chromium yet: install it once, then retry.
        print("No usable browser found — installing Playwright Chromium (one-time download)…", flush=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
        try:
            return self._pw.chromium.launch_persistent_context(str(self._profile_dir), headless=self._headless)
        except Exception as e:
            errors.append(f"chromium (after install): {str(e).splitlines()[0]}")
        raise RuntimeError("Could not launch a browser for Blackboard:\n  " + "\n  ".join(errors))

    # ── cookie persistence ───────────────────────────────────────────────────
    def _restore_cookies(self) -> None:
        path = self._profile_dir / _COOKIE_FILE
        if not path.exists():
            return
        try:
            self._context.add_cookies(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            pass  # stale/corrupt snapshot — a fresh login will overwrite it

    def _save_cookies(self) -> None:
        path = self._profile_dir / _COOKIE_FILE
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._context.cookies()), encoding="utf-8")
        tmp.replace(path)

    # ── auth ─────────────────────────────────────────────────────────────────
    def _on_bb(self, page) -> bool:
        try:
            return urlparse(page.url).hostname == self.host
        except Exception:
            return False

    def _me_from(self, page) -> dict | None:
        """users/me via in-page fetch, or None if not authenticated / not on Blackboard."""
        if not self._on_bb(page):
            return None
        try:
            value = page.evaluate(_FETCH_JS, {"path": ME_PATH, "params": {}})
            if value.get("status") == 200 and value.get("body"):
                return value["body"]
        except Exception as e:  # page navigated mid-evaluate, or the page's JS world is unusable
            print(f"[auth] in-page check failed: {str(e).splitlines()[0][:120]}", file=sys.stderr, flush=True)
        # Fallback: a direct request sharing the browser's cookie jar.
        try:
            r = self._context.request.get(self._base + ME_PATH, headers={"Accept": "application/json"})
            if r.ok:
                return r.json()
        except Exception as e:
            print(f"[auth] direct check failed: {str(e).splitlines()[0][:120]}", file=sys.stderr, flush=True)
        return None

    def ensure_logged_in(self, silent_timeout: float = 20.0) -> dict | None:
        """Return the current user if the saved session works, else None.

        Tries the restored session first, then a silent SSO round-trip (works when the
        identity provider remembers the user), without ever showing a window.
        """
        try:
            self._page.goto(self._base + ME_PATH, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass
        me = self._me_from(self._page)
        if not me:
            try:
                self._page.goto(self._base + "/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            deadline = time.time() + silent_timeout
            last_url, still_since = None, time.time()
            while not me and time.time() < deadline:
                self._page.wait_for_timeout(1000)
                me = self._me_from(self._page)
                url = self._page.url
                if url != last_url:
                    last_url, still_since = url, time.time()
                elif not self._on_bb(self._page) and time.time() - still_since > 4:
                    break  # parked on the identity provider's sign-in form: needs a real login
        if me:
            self._save_cookies()
        return me

    def interactive_login(self, timeout: float = 600.0) -> dict | None:
        """Open Blackboard in the (headed) window and wait for the user to finish logging in."""
        me = self.ensure_logged_in(silent_timeout=5.0)
        if me:
            return me
        try:
            self._page.bring_to_front()
            if not self._on_bb(self._page):
                self._page.goto(self._base + "/", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                pages = [p for p in self._context.pages if not p.is_closed()]
            except Exception:
                return None  # browser window was closed
            if not pages:
                return None
            for p in pages:
                me = self._me_from(p)
                if me:
                    self._page = p
                    self._save_cookies()
                    return me
            time.sleep(2)
        return None

    # ── API used by BlackboardClient ─────────────────────────────────────────
    def fetch_json(self, path: str, params: dict | None = None) -> dict:
        if not self._on_bb(self._page):
            self._page.goto(self._base + ME_PATH, wait_until="domcontentloaded", timeout=30000)
        try:
            value = self._page.evaluate(_FETCH_JS, {"path": path, "params": params or {}})
        except Exception as e:
            raise RuntimeError(f"fetch() failed in Blackboard page: {e}") from e
        status = value.get("status", 0)
        if not (200 <= status < 300):
            fake = requests.Response()
            fake.status_code = status
            raise requests.HTTPError(f"HTTP {status} for {path}", response=fake)
        return value.get("body") or {}

    def download_sharepoint(self, url: str) -> tuple[str, bytes] | None:
        """Fetch a university SharePoint file linked from a course page.

        SharePoint needs the Microsoft sign-in, which the profile already holds:
        visiting the site once in a page completes SSO, after which the context's
        request client can download directly. Dead links (files moved or converted,
        e.g. a .docx republished as .pdf) fall back to the same name with the other
        document extension. Returns (file name, bytes), or None if nothing is there.
        """
        host = urlparse(url).hostname
        if host not in self._sso_hosts:
            page = self._context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass  # a file URL may start a download or 404 — SSO has completed either way
            finally:
                page.close()
            self._sso_hosts.add(host)
        for candidate in sharepoint_candidates(url):
            try:
                r = self._context.request.get(candidate + "?download=1", timeout=120000)
            except Exception:
                continue
            if r.ok and "text/html" not in r.headers.get("content-type", ""):
                return unquote(candidate.rsplit("/", 1)[-1]), r.body()
        return None

    def cookie_jar(self) -> requests.cookies.RequestsCookieJar:
        """Browser cookies as a domain-scoped jar, so requests only sends them to matching hosts."""
        jar = requests.cookies.RequestsCookieJar()
        for c in self._context.cookies():
            jar.set(c["name"], c["value"], domain=c["domain"], path=c.get("path") or "/",
                    secure=bool(c.get("secure")))
        return jar
