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
        [path, "--remote-debugging-port=9222", "--remote-allow-origins=http://127.0.0.1:9222",
         "--no-first-run", "--no-default-browser-check", "about:blank"],
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


def _open_url_in_browser(port: int, url: str) -> None:
    try:
        from urllib.parse import quote
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/new?{quote(url, safe='')}", timeout=5)
    except Exception:
        pass


def _wait_for_login(domain: str, port: int, timeout: float = 120.0) -> bool:
    """Poll until cookies for domain appear in the browser. Returns True when found."""
    from cookie_extractor import _extract_via_cdp
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if _extract_via_cdp(domain, port):
                return True
        except RuntimeError:
            # Expected while the user is mid-login; print a dot to show progress
            print(".", end="", flush=True)
        except Exception:
            pass
        time.sleep(2)
    return False


def run_wizard() -> None:
    """
    Terminal wizard: detect browsers, launch one with remote debugging,
    open Blackboard, and wait for login automatically.
    Exits the process if setup cannot complete.
    """
    from urllib.parse import urlparse
    from config import BB_BASE_URL

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

    if len(browsers) == 1:
        name, path = browsers[0]
        print(f"Detected: {name}")
    else:
        print("Detected browsers:")
        for i, (name, _) in enumerate(browsers, 1):
            print(f"  [{i}] {name}")
        print()
        try:
            raw = input("Pick a browser [1]: ").strip() or "1"
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

    print(f"Opening {BB_BASE_URL}...")
    _open_url_in_browser(9222, BB_BASE_URL)

    domain = urlparse(BB_BASE_URL).netloc
    print("Please log in to Blackboard in the browser window.", flush=True)
    print("Waiting for login", end="", flush=True)

    if _wait_for_login(domain, 9222):
        print(" ✓")
        print()
    else:
        print()
        print("Timed out waiting for Blackboard login. Please log in and re-run.")
        sys.exit(1)
