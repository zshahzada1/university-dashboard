# One-Click Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard runnable cross-platform with `uv run start.py` — no manual venv setup, no Node.js, includes a terminal browser wizard for the CDP debug port.

**Architecture:** A PEP 723 inline-script `start.py` at the repo root declares all Python deps; `uv` manages a single venv automatically. A new `browser_launcher.py` handles OS detection and launching Chrome/Edge with `--remote-debugging-port=9222` before the server starts. The pre-built `frontend/dist/` is committed so friends skip Node.

**Tech Stack:** Python 3.11+, uv (PEP 723 inline scripts), FastAPI/uvicorn, websocket-client, requests

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `start.py` | Create | uv entry point, path wiring, browser check, uvicorn launch |
| `run.sh` | Modify | Thin wrapper → `uv run start.py`; keep `dev` mode |
| `run.bat` | Create | Windows double-click launcher |
| `sync/scripts/bb_sync/browser_launcher.py` | Create | OS detect, find browsers, launch, wizard |
| `sync/scripts/bb_sync/test_browser_launcher.py` | Create | Unit tests for browser_launcher |
| `sync/scripts/bb_sync/test_cookie_extractor.py` | Modify | Fix tests that reference removed functions |
| `.gitignore` | Modify | Remove `frontend/dist/` exclusion |
| `frontend/.gitignore` | Modify | Remove `dist` line |
| `frontend/dist/` | Build + commit | Pre-built frontend |
| `README.md` | Rewrite | 3-step setup, browser instructions |
| `sync/README.md` | Update | Remove venv setup requirement |

---

### Task 1: Fix test_cookie_extractor.py

The simplified `cookie_extractor.py` removed `_extract_via_cdp(domain)` (PowerShell version), `_CDP_PS_CMD`, `_WINDOWS_MANUAL_EXPORT_EXTRA_WSL`, and the browser_cookie3 fallbacks. The existing tests reference these — they must be rewritten to match the new API.

**New `cookie_extractor.py` public surface:**
- `extract_bb_cookies(force_refresh=False) -> dict`
- `_cdp_port() -> int | None`
- `_extract_via_cdp(domain, port) -> dict`  (now takes port arg)
- `_save_cache(path, cookies) -> None`

**Files:**
- Modify: `sync/scripts/bb_sync/test_cookie_extractor.py`

- [ ] **Step 1: Replace test_cookie_extractor.py**

```python
# sync/scripts/bb_sync/test_cookie_extractor.py
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")
from cookie_extractor import extract_bb_cookies, _cdp_port, _extract_via_cdp


class TestCdpPort(unittest.TestCase):
    def test_returns_port_when_reachable(self):
        with patch("cookie_extractor.urllib.request.urlopen") as mock_open:
            mock_open.return_value = MagicMock()
            result = _cdp_port()
        self.assertEqual(result, 9222)

    def test_returns_none_when_unreachable(self):
        with patch("cookie_extractor.urllib.request.urlopen", side_effect=OSError):
            result = _cdp_port()
        self.assertIsNone(result)


class TestExtractViaCdp(unittest.TestCase):
    def _ws_mock(self, cookies):
        ws = MagicMock()
        ws.recv.return_value = json.dumps({"result": {"cookies": cookies}})
        return ws

    def test_returns_matching_cookies(self):
        cookies = [
            {"name": "BbRouter", "value": "abc", "domain": ".brighton.ac.uk"},
            {"name": "other", "value": "x", "domain": ".example.com"},
        ]
        ws = self._ws_mock(cookies)
        with patch("cookie_extractor.urllib.request.urlopen") as mock_open, \
             patch("cookie_extractor._ws.WebSocket", return_value=ws):
            mock_open.return_value = MagicMock(
                read=lambda: json.dumps([{"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/page/1"}]).encode()
            )
            result = _extract_via_cdp("brighton.ac.uk", 9222)
        self.assertIn("BbRouter", result)
        self.assertNotIn("other", result)

    def test_raises_when_no_matching_cookies(self):
        ws = self._ws_mock([])
        with patch("cookie_extractor.urllib.request.urlopen") as mock_open, \
             patch("cookie_extractor._ws.WebSocket", return_value=ws):
            mock_open.return_value = MagicMock(
                read=lambda: json.dumps([{"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/page/1"}]).encode()
            )
            with self.assertRaises(RuntimeError):
                _extract_via_cdp("brighton.ac.uk", 9222)

    def test_raises_when_websocket_client_missing(self):
        import sys
        with patch.dict(sys.modules, {"websocket": None}):
            with self.assertRaises(RuntimeError, msg="websocket-client not installed"):
                _extract_via_cdp("brighton.ac.uk", 9222)


class TestExtractBbCookies(unittest.TestCase):
    def test_returns_cached_cookies_when_fresh(self, tmp_path=None):
        cached = {"BbRouter": "cached"}
        with patch("cookie_extractor.Path") as MockPath:
            mock_cache = MagicMock()
            mock_cache.exists.return_value = True
            mock_cache.stat.return_value = MagicMock(st_mtime=time.time() - 60)
            mock_cache.read_text.return_value = json.dumps(cached)
            mock_cache.parent = MagicMock()
            MockPath.return_value = mock_cache
            result = extract_bb_cookies(force_refresh=False)
        self.assertEqual(result["BbRouter"], "cached")

    def test_raises_when_cdp_not_reachable(self):
        with patch("cookie_extractor._cdp_port", return_value=None), \
             patch("cookie_extractor.Path") as MockPath:
            mock_cache = MagicMock()
            mock_cache.exists.return_value = False
            MockPath.return_value = mock_cache
            with self.assertRaises(RuntimeError) as ctx:
                extract_bb_cookies(force_refresh=True)
        self.assertIn("debug port", str(ctx.exception))

    def test_extracts_and_caches_on_cache_miss(self):
        cookies = {"BbRouter": "fresh"}
        with patch("cookie_extractor._cdp_port", return_value=9222), \
             patch("cookie_extractor._extract_via_cdp", return_value=cookies), \
             patch("cookie_extractor._save_cache") as mock_save, \
             patch("cookie_extractor.Path") as MockPath:
            mock_cache = MagicMock()
            mock_cache.exists.return_value = False
            MockPath.return_value = mock_cache
            result = extract_bb_cookies(force_refresh=True)
        self.assertEqual(result["BbRouter"], "fresh")
        mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to confirm they pass**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync
python -m pytest test_cookie_extractor.py -v 2>&1
```

Expected: all tests pass (some may need `_ws` import alias — if so, add `import websocket as _ws` at top of cookie_extractor.py in the `_extract_via_cdp` function scope where it already exists).

- [ ] **Step 3: Commit**

```bash
git add sync/scripts/bb_sync/test_cookie_extractor.py
git commit -m "test(sync): update cookie_extractor tests for simplified CDP-only extractor"
```

---

### Task 2: Create browser_launcher.py

**Files:**
- Create: `sync/scripts/bb_sync/browser_launcher.py`

- [ ] **Step 1: Create browser_launcher.py**

```python
# sync/scripts/bb_sync/browser_launcher.py
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def cdp_reachable(ports: tuple[int, ...] = (9222, 9223), timeout: float = 2.0) -> bool:
    for port in ports:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=timeout)
            return True
        except Exception:
            pass
    return False


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except Exception:
        return False


def find_browsers() -> list[tuple[str, str]]:
    """Return [(display_name, executable_path)] for every browser found on this machine."""
    system = platform.system()
    browsers: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add(name: str, path: str) -> None:
        if name not in seen and Path(path).exists():
            seen.add(name)
            browsers.append((name, path))

    if system == "Darwin":
        _add("Google Chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        _add("Microsoft Edge", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
        _add("Chromium", "/Applications/Chromium.app/Contents/MacOS/Chromium")

    elif system == "Linux":
        if _is_wsl():
            # WSL2 can execute Windows binaries directly via /mnt/c/...
            _add("Microsoft Edge", "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
            _add("Google Chrome", "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe")
            _add("Google Chrome", "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe")
        else:
            for name, cmd in [
                ("Google Chrome", "google-chrome"),
                ("Chromium", "chromium-browser"),
                ("Chromium", "chromium"),
                ("Microsoft Edge", "microsoft-edge"),
            ]:
                if name not in seen and shutil.which(cmd):
                    seen.add(name)
                    browsers.append((name, cmd))

    elif system == "Windows":
        _add("Microsoft Edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
        _add("Microsoft Edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
        _add("Google Chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        _add("Google Chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")

    return browsers


def launch_browser(path: str) -> None:
    subprocess.Popen(
        [path, "--remote-debugging-port=9222", "--no-first-run",
         "--no-default-browser-check", "about:blank"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_cdp(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cdp_reachable(timeout=1.0):
            return True
        time.sleep(0.5)
    return False


def run_wizard() -> None:
    """
    Terminal wizard: detect browsers, prompt user to pick one, launch it,
    wait for Blackboard login. Exits the process if setup cannot complete.
    """
    print()
    print("No browser debug port found. Let's open one for you.")
    print()

    browsers = find_browsers()
    if not browsers:
        print("No supported browser detected on this machine.")
        print()
        print("Start Chrome or Edge manually with:")
        print("  chrome --remote-debugging-port=9222")
        print("  msedge --remote-debugging-port=9222")
        print()
        print("Then re-run:  uv run start.py")
        sys.exit(1)

    print("Detected browsers:")
    for i, (name, _) in enumerate(browsers, 1):
        print(f"  [{i}] {name}")
    print()

    try:
        raw = input(f"Pick a browser [1]: ").strip() or "1"
        idx = int(raw) - 1
        if not (0 <= idx < len(browsers)):
            raise ValueError
    except (ValueError, EOFError):
        print("Invalid choice — using option 1.")
        idx = 0

    name, path = browsers[idx]
    print(f"Launching {name} with remote debugging...")
    launch_browser(path)

    if not _wait_for_cdp(timeout=20.0):
        print()
        print(f"Could not connect to {name} on port 9222 after 20 seconds.")
        print("Try starting it manually with --remote-debugging-port=9222 and re-run.")
        sys.exit(1)

    print()
    input("Log in to Blackboard in the browser window, then press Enter to continue: ")
    print()
```

- [ ] **Step 2: Commit**

```bash
git add sync/scripts/bb_sync/browser_launcher.py
git commit -m "feat(sync): add browser_launcher — OS detection and debug-port launch wizard"
```

---

### Task 3: Create test_browser_launcher.py

**Files:**
- Create: `sync/scripts/bb_sync/test_browser_launcher.py`

- [ ] **Step 1: Write the tests**

```python
# sync/scripts/bb_sync/test_browser_launcher.py
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, ".")
import browser_launcher as bl


class TestCdpReachable(unittest.TestCase):
    def test_true_when_port_responds(self):
        with patch("browser_launcher.urllib.request.urlopen"):
            self.assertTrue(bl.cdp_reachable())

    def test_false_when_all_ports_fail(self):
        with patch("browser_launcher.urllib.request.urlopen", side_effect=OSError):
            self.assertFalse(bl.cdp_reachable())


class TestIsWsl(unittest.TestCase):
    def test_true_when_proc_version_contains_microsoft(self):
        with patch("browser_launcher.Path") as MockPath:
            MockPath.return_value.read_text.return_value = "Linux version ... microsoft-standard-WSL2"
            self.assertTrue(bl._is_wsl())

    def test_false_when_proc_version_missing(self):
        with patch("browser_launcher.Path") as MockPath:
            MockPath.return_value.read_text.side_effect = FileNotFoundError
            self.assertFalse(bl._is_wsl())

    def test_false_on_plain_linux(self):
        with patch("browser_launcher.Path") as MockPath:
            MockPath.return_value.read_text.return_value = "Linux version 6.1.0-generic #1 SMP"
            self.assertFalse(bl._is_wsl())


class TestFindBrowsers(unittest.TestCase):
    def _platform(self, system, is_wsl=False):
        """Context: mock platform.system and _is_wsl together."""
        return (
            patch("browser_launcher.platform.system", return_value=system),
            patch("browser_launcher._is_wsl", return_value=is_wsl),
        )

    def test_mac_finds_chrome_when_installed(self):
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        with patch("browser_launcher.platform.system", return_value="Darwin"), \
             patch("browser_launcher.Path") as MockPath:
            MockPath.return_value.exists.return_value = False
            # Only Chrome exists
            MockPath.side_effect = lambda p: MagicMock(exists=lambda: str(p) == chrome_path)
            browsers = bl.find_browsers()
        names = [b[0] for b in browsers]
        self.assertIn("Google Chrome", names)

    def test_mac_empty_when_nothing_installed(self):
        with patch("browser_launcher.platform.system", return_value="Darwin"), \
             patch("browser_launcher.Path") as MockPath:
            MockPath.return_value.exists.return_value = False
            MockPath.side_effect = lambda p: MagicMock(exists=lambda: False)
            self.assertEqual(bl.find_browsers(), [])

    def test_wsl_finds_edge(self):
        edge_wsl = "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
        with patch("browser_launcher.platform.system", return_value="Linux"), \
             patch("browser_launcher._is_wsl", return_value=True), \
             patch("browser_launcher.Path") as MockPath:
            MockPath.side_effect = lambda p: MagicMock(exists=lambda: str(p) == edge_wsl)
            browsers = bl.find_browsers()
        self.assertTrue(any(b[0] == "Microsoft Edge" for b in browsers))

    def test_linux_uses_which(self):
        with patch("browser_launcher.platform.system", return_value="Linux"), \
             patch("browser_launcher._is_wsl", return_value=False), \
             patch("browser_launcher.shutil.which", side_effect=lambda cmd: "/usr/bin/google-chrome" if cmd == "google-chrome" else None):
            browsers = bl.find_browsers()
        self.assertTrue(any(b[0] == "Google Chrome" for b in browsers))

    def test_no_duplicates_when_multiple_paths_match(self):
        with patch("browser_launcher.platform.system", return_value="Windows"), \
             patch("browser_launcher.Path") as MockPath:
            MockPath.side_effect = lambda p: MagicMock(exists=lambda: True)
            browsers = bl.find_browsers()
        names = [b[0] for b in browsers]
        self.assertEqual(len(names), len(set(names)), "Duplicate browser names found")


class TestRunWizard(unittest.TestCase):
    def test_exits_when_no_browsers_found(self):
        with patch("browser_launcher.find_browsers", return_value=[]), \
             self.assertRaises(SystemExit) as cm:
            bl.run_wizard()
        self.assertEqual(cm.exception.code, 1)

    def test_launches_selected_browser_and_waits(self):
        browsers = [("Google Chrome", "/usr/bin/google-chrome")]
        with patch("browser_launcher.find_browsers", return_value=browsers), \
             patch("browser_launcher.launch_browser") as mock_launch, \
             patch("browser_launcher._wait_for_cdp", return_value=True), \
             patch("builtins.input", side_effect=["1", ""]):
            bl.run_wizard()
        mock_launch.assert_called_once_with("/usr/bin/google-chrome")

    def test_defaults_to_first_browser_on_empty_input(self):
        browsers = [("Chrome", "/a"), ("Edge", "/b")]
        with patch("browser_launcher.find_browsers", return_value=browsers), \
             patch("browser_launcher.launch_browser") as mock_launch, \
             patch("browser_launcher._wait_for_cdp", return_value=True), \
             patch("builtins.input", side_effect=["", ""]):
            bl.run_wizard()
        mock_launch.assert_called_once_with("/a")

    def test_exits_when_browser_never_opens_port(self):
        browsers = [("Chrome", "/a")]
        with patch("browser_launcher.find_browsers", return_value=browsers), \
             patch("browser_launcher.launch_browser"), \
             patch("browser_launcher._wait_for_cdp", return_value=False), \
             patch("builtins.input", return_value="1"), \
             self.assertRaises(SystemExit) as cm:
            bl.run_wizard()
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync
python -m pytest test_browser_launcher.py -v 2>&1
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add sync/scripts/bb_sync/test_browser_launcher.py
git commit -m "test(sync): add browser_launcher test suite"
```

---

### Task 4: Create start.py

**Files:**
- Create: `start.py`

- [ ] **Step 1: Create start.py**

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastapi>=0.110",
#   "uvicorn[standard]>=0.27",
#   "pydantic>=2.6",
#   "websocket-client>=1.7",
#   "requests>=2.31",
# ]
# ///
from __future__ import annotations

import os
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).parent.resolve()

# ── Python path: backend app + bb_sync module ────────────────────────────────
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "sync" / "scripts" / "bb_sync"))

# ── bb_sync env: reuse this managed venv for the sync subprocess ─────────────
os.environ.setdefault("BBSYNC_PYTHON", sys.executable)
os.environ.setdefault("BBSYNC_SCRIPTS_DIR", str(ROOT / "sync" / "scripts"))


def _cdp_reachable() -> bool:
    for port in (9222, 9223):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
            return True
        except Exception:
            pass
    return False


if not _cdp_reachable():
    from browser_launcher import run_wizard  # type: ignore[import]
    run_wizard()

# ── start server ─────────────────────────────────────────────────────────────
os.chdir(ROOT / "backend")
import uvicorn  # noqa: E402 — after path setup

print(f"\nStarting server → http://localhost:8765\n")
uvicorn.run("app.main:app", host="127.0.0.1", port=8765)
```

- [ ] **Step 2: Smoke-test: verify uv can read the inline deps**

```bash
cd /home/zozo/University/dashboard
uv run --dry-run start.py 2>&1 | head -20
```

Expected: uv lists the deps it would install (or says "all packages already installed") — no errors.

- [ ] **Step 3: Commit**

```bash
git add start.py
git commit -m "feat: add uv inline-script entry point (start.py) with browser wizard"
```

---

### Task 5: Update run.sh + create run.bat

**Files:**
- Modify: `run.sh`
- Create: `run.bat`

- [ ] **Step 1: Update run.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "dev" ]; then
  ( cd backend && .venv/bin/uvicorn app.main:app --reload --port 8765 ) &
  BPID=$!
  ( cd frontend && npm run dev ) &
  FPID=$!
  trap "kill $BPID $FPID 2>/dev/null || true" EXIT
  wait
else
  exec uv run start.py
fi
```

- [ ] **Step 2: Create run.bat**

```batch
@echo off
uv run start.py
pause
```

- [ ] **Step 3: Commit**

```bash
git add run.sh run.bat
git commit -m "feat: simplify run.sh to uv run start.py; add run.bat for Windows"
```

---

### Task 6: Commit pre-built frontend/dist

**Files:**
- Modify: `.gitignore` (root) — remove `frontend/dist/`
- Modify: `frontend/.gitignore` — remove `dist` line
- Build and commit `frontend/dist/`

- [ ] **Step 1: Remove frontend/dist from both gitignores**

In root `.gitignore`, remove the line:
```
frontend/dist/
```

In `frontend/.gitignore`, remove the line:
```
dist
```
(leave `dist-ssr` if present)

- [ ] **Step 2: Build the frontend**

```bash
cd /home/zozo/University/dashboard/frontend
npm run build 2>&1 | tail -5
```

Expected: `dist/index.html` and `dist/assets/` created.

- [ ] **Step 3: Verify backend serves it**

```bash
ls /home/zozo/University/dashboard/frontend/dist/
```

Expected: `index.html`, `assets/`, `favicon.svg`, `icons.svg`

- [ ] **Step 4: Commit**

```bash
cd /home/zozo/University/dashboard
git add .gitignore frontend/.gitignore frontend/dist/
git commit -m "feat: commit pre-built frontend/dist so friends skip Node.js"
```

---

### Task 7: Update README.md and sync/README.md

**Files:**
- Modify: `README.md`
- Modify: `sync/README.md`

- [ ] **Step 1: Rewrite README.md**

```markdown
# University Dashboard

Local study hub for grades, deadlines, files, tasks, notes, and topic confidence across all Blackboard modules.

## Quick Start

**Step 1 — install [uv](https://docs.astral.sh/uv/) (one-time, ~30 seconds)**

```bash
# Mac / Linux / WSL2
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Step 2 — clone**

```bash
git clone https://github.com/zshahzada1/university-dashboard.git
cd university-dashboard
```

**Step 3 — run**

```bash
uv run start.py        # Mac / Linux / WSL2
run.bat                # Windows (double-click or terminal)
```

On first run, if no browser debug port is detected, the app walks you through opening Chrome or Edge with remote debugging enabled. Log in to Blackboard when prompted, press Enter, and the server starts at **http://localhost:8765**.

> **Why the debug port?** Blackboard session cookies are extracted live from your running browser — your password is never stored or transmitted.

## Syncing Blackboard

Use the **Sync** page in the dashboard to pull the latest files and grades. You can also run it from the terminal:

```bash
# Files + grades for specific modules
cd sync && bash sync.sh --modules FA565 FN585 FA583

# Grades only (all modules)
cd sync && bash sync.sh --grades

# Force cookie refresh (if auth fails)
cd sync && bash sync.sh --refresh-cookies
```

See [`sync/README.md`](sync/README.md) for full sync documentation.

## Features

| Section | Description |
|---|---|
| Grades | Live grade view with module breakdowns, weighted averages, and projections |
| Files | File tree browser for all synced Blackboard content |
| Assignments | Deadline tracker with status and Blackboard links |
| Tasks | Personal to-do list per module |
| Events | Calendar of upcoming events and deadlines |
| Notes | Per-module markdown notes |
| Topics | Confidence tracker for syllabus topics |
| Search | Full-text search across files and notes |
| Sync | In-browser trigger for Blackboard file + grade sync |

## Architecture

```
dashboard/
  start.py      — uv entry point (PEP 723 inline script)
  run.sh        — Mac/Linux/WSL2 launcher
  run.bat       — Windows launcher
  backend/      — FastAPI (Python 3.12), port 8765
  frontend/     — React + TypeScript + Vite (pre-built dist/ committed)
  sync/         — bb_sync CLI: Blackboard file + grade sync
```

## Development

```bash
# Hot-reload dev mode (requires Node.js + manual venv setup)
./run.sh dev
# frontend: http://localhost:5173
# backend:  http://localhost:8765
```

**Backend venv (for dev/tests):**
```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

**Frontend:**
```bash
cd frontend && npm install && npm run dev
```

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `UNI_DIR` | `~/University` | Root folder for synced course files |
| `UNI_DATA_DIR` | `backend/data/` | JSON data directory |
| `BBSYNC_PYTHON` | `sys.executable` (set by start.py) | Python for bb_sync subprocess |
| `BBSYNC_SCRIPTS_DIR` | `sync/scripts/` | Working directory for bb_sync |
| `BB_BASE_URL` | `https://studentcentral.brighton.ac.uk` | Blackboard instance URL |
```

- [ ] **Step 2: Update sync/README.md — simplify prerequisites**

Replace the Prerequisites and Installation sections with:

```markdown
## Prerequisites

| Requirement | Notes |
|---|---|
| uv | Installed via the dashboard Quick Start |
| Chrome or Edge | Must be open and logged into Blackboard |

No manual venv setup needed — `uv run start.py` handles Python and all dependencies automatically.

## Manual venv (for development/testing only)

```bash
cd sync/scripts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
```

- [ ] **Step 3: Commit**

```bash
git add README.md sync/README.md
git commit -m "docs: rewrite README for uv one-click setup; update sync/README prerequisites"
```

---

### Task 8: Push to GitHub

- [ ] **Step 1: Verify all tests still pass**

```bash
cd /home/zozo/University/dashboard/sync/scripts/bb_sync
python -m pytest test_cookie_extractor.py test_browser_launcher.py -v 2>&1
```

Expected: all tests pass.

- [ ] **Step 2: Review what we're pushing**

```bash
git log origin/main..HEAD --oneline
```

Expected: 7–8 commits since last push.

- [ ] **Step 3: Push**

```bash
git push origin main
```

Expected: push succeeds, GitHub shows the new commits.
