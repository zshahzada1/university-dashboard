import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from config import BB_BASE_URL, COOKIE_CACHE

# --- browser_cookie3 fallback (legacy, broken on Edge 127+ due to App-Bound Encryption) ---
_WINDOWS_SCRIPT_LINES = [
    "import browser_cookie3, json, sys",
    "domain = sys.argv[1]",
    "cj = browser_cookie3.edge(domain_name=domain)",
    "print(json.dumps({c.name: c.value for c in cj}))",
]
_WINDOWS_SCRIPT = "; ".join(_WINDOWS_SCRIPT_LINES)

_WINDOWS_MANUAL_EXPORT = "C:\\cookies_bb.json"
_WINDOWS_MANUAL_EXPORT_WSL = "/mnt/c/cookies_bb.json"

# Additional locations to check for manually exported cookies
_WINDOWS_MANUAL_EXPORT_EXTRA_WSL = [
    "/mnt/c/Users/zhbsh/cookies_bb.json",
]

# --- CDP cookie extraction ---
# Edge binds --remote-debugging-port to 127.0.0.1 (Windows loopback) which is not
# reachable from WSL2. The CDP client therefore runs on Windows Python, same as
# browser_cookie3, so it can connect to localhost:9222 directly.
# Requires: pip install websocket-client  (in Windows Python)
_CDP_WIN_SCRIPT = "\n".join([
    "import time, json, sys, requests, websocket",
    "domain = sys.argv[1]",
    "base = 'http://localhost:9222'",
    "ready = False",
    "for _ in range(20):",
    "    try:",
    "        if requests.get(base+'/json/version', timeout=1).status_code == 200:",
    "            ready = True; break",
    "    except Exception: pass",
    "    time.sleep(0.5)",
    "if not ready: raise SystemExit('CDP not ready within 10s')",
    "targets = requests.get(base+'/json', timeout=5).json()",
    "pts = [t for t in targets if t.get('type') == 'page']",
    "ws_url = (pts[0]['webSocketDebuggerUrl'] if pts",
    "          else requests.get(base+'/json/new', timeout=5).json()['webSocketDebuggerUrl'])",
    "ws = websocket.WebSocket()",
    "ws.connect(ws_url, timeout=10); ws.settimeout(10)",
    "ws.send(json.dumps({'id': 1, 'method': 'Network.getAllCookies'}))",
    "r = json.loads(ws.recv()); ws.close()",
    "print(json.dumps({c['name']: c['value'] for c in r['result']['cookies']",
    "                  if (lambda d: domain in d or d.lstrip('.') in domain)(c.get('domain', ''))}))",
])

# Written to Windows Temp (accessible from WSL via /mnt/c/...) before each CDP run
_CDP_SCRIPT_WIN = r"C:\Windows\Temp\bb_cdp_extract.py"
_CDP_SCRIPT_WSL = "/mnt/c/Windows/Temp/bb_cdp_extract.py"

# PowerShell command template — {domain} is substituted at call time via .replace().
# Uses .format(script=...) at module load, leaving {domain} as a literal placeholder.
#
# Launch strategy: Start-Job (NOT Start-Process) to bypass Edge's singleton detection.
# Start-Process causes Edge to signal the existing singleton and exit without binding
# the debug port. Start-Job runs Edge in a background job session, which avoids the
# singleton check and makes Edge reliably bind --remote-debugging-port=9222.
#
# Steps: kill existing Edge → launch via Start-Job → try: run CDP script
#        finally: stop job + kill all msedge.
_CDP_PS_CMD = (
    # Only kill and restart Edge if CDP is not already reachable on :9222.
    # This preserves the user's open browser when they've already launched Edge
    # with --remote-debugging-port=9222 themselves.
    '$cdpReady = ($null -ne (curl.exe -s -o NUL -w "%{{http_code}}" --max-time 2 http://localhost:9222/json/version 2>$null) -and '
    '(curl.exe -s -o NUL -w "%{{http_code}}" --max-time 2 http://localhost:9222/json/version 2>$null) -eq "200"); '
    'if (-not $cdpReady) {{ '
    '  Stop-Process -Name msedge -Force -ErrorAction SilentlyContinue; '
    '  Start-Sleep -Milliseconds 800 '
    '}}; '
    '$ed = if (Test-Path "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe") '
    '{{ "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" }} '
    'else {{ "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe" }}; '
    '$ud = "$env:LOCALAPPDATA\\Microsoft\\Edge\\User Data"; '
    '$job = if (-not $cdpReady) {{ '
    '  Start-Job -ArgumentList $ed, $ud {{ '
    '    param($e, $d); '
    '    & $e "--remote-debugging-port=9222" "--remote-allow-origins=*" "--user-data-dir=$d" "--no-first-run" "--no-default-browser-check" "about:blank" '
    '  }} '
    '}} else {{ $null }}; '
    'try {{ '
    # Poll for CDP readiness in PowerShell before invoking Python.
    # Edge can take 8-12s to start in a Start-Job context — poll up to 20s (40×0.5s).
    # Use curl.exe (ships with Windows 10+) — more reliable than Invoke-WebRequest
    # in non-interactive PowerShell sessions (avoids proxy/TLS policy issues).
    '  $ok = $false; '
    '  for ($i = 0; $i -lt 40; $i++) {{ '
    '    $r = curl.exe -s -o NUL -w "%{{http_code}}" --max-time 1 http://localhost:9222/json/version 2>$null; '
    '    if ($r -eq "200") {{ $ok = $true; break }}; '
    '    Start-Sleep -Milliseconds 500 '
    '  }}; '
    '  if (-not $ok) {{ throw "CDP not ready within 20s" }}; '
    '  $py = $null; '
    '  foreach ($c in @("py", "python")) {{ '
    '    try {{ & $c --version 2>&1 | Out-Null; if ($LASTEXITCODE -eq 0) {{ $py = $c; break }} }} '
    '    catch {{}} '
    '  }}; '
    '  if (-not $py) {{ throw "No Python found in Windows PATH" }}; '
    '  & $py "{script}" {{domain}} '
    '}} finally {{ '
    '  if ($job) {{ Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -ErrorAction SilentlyContinue }} '
    '}}'
).format(script=_CDP_SCRIPT_WIN)


def _cdp_reachable(timeout: float = 3.0) -> bool:
    """Return True if Edge's CDP port is reachable on 127.0.0.1:9222."""
    try:
        urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=timeout)
        return True
    except Exception:
        return False


def _extract_via_wsl_cdp(domain: str) -> dict:
    """
    Extract cookies directly from Edge via CDP WebSocket, running entirely in WSL2 Python.
    Requires websocket-client (pip install websocket-client) and Edge running with
    --remote-debugging-port=9222 reachable on 127.0.0.1 (WSL2 mirrored networking).
    Raises RuntimeError on any failure.
    """
    try:
        import websocket as _ws
    except ImportError as e:
        raise RuntimeError("websocket-client not installed — run: pip install websocket-client") from e

    if not _cdp_reachable(timeout=3.0):
        raise RuntimeError("CDP at 127.0.0.1:9222 not reachable — Edge not running with debug port")

    try:
        raw = urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read()
        targets = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Could not list CDP targets: {e}") from e

    pages = [t for t in targets if t.get("type") == "page"]
    if pages:
        ws_url = pages[0]["webSocketDebuggerUrl"]
    else:
        try:
            new_raw = urllib.request.urlopen("http://127.0.0.1:9222/json/new", timeout=5).read()
            ws_url = json.loads(new_raw)["webSocketDebuggerUrl"]
        except Exception as e:
            raise RuntimeError(f"No CDP page targets available: {e}") from e

    # Replace 'localhost' with '127.0.0.1' so it routes through WSL2 mirrored networking
    ws_url = ws_url.replace("localhost", "127.0.0.1")

    try:
        ws = _ws.WebSocket()
        ws.connect(ws_url, timeout=10)
        ws.settimeout(10)
        ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies"}))
        result = json.loads(ws.recv())
        ws.close()
    except Exception as e:
        raise RuntimeError(f"CDP WebSocket call failed: {e}") from e

    cookies_raw = result.get("result", {}).get("cookies", [])
    filtered = {
        c["name"]: c["value"]
        for c in cookies_raw
        if domain in c.get("domain", "") or c.get("domain", "").lstrip(".") in domain
    }
    if not filtered:
        raise RuntimeError(f"No cookies found for {domain} — make sure you are logged into Blackboard in Edge")
    return filtered


_BROWSER_HARNESS_SCRIPT = "\n".join([
    "import json",
    "result = cdp('Network.getAllCookies', {})",
    "cookies = result.get('cookies', [])",
    "bb = {c['name']: c['value'] for c in cookies if '__DOMAIN__' in c.get('domain', '')}",
    "print(json.dumps(bb))",
])


def _extract_via_browser_harness(domain: str) -> dict:
    """
    Extract cookies via browser-harness connecting to Edge's CDP endpoint on 127.0.0.1:9222.
    Requires Edge to be running with --remote-debugging-port=9222.
    Raises RuntimeError on failure.
    """
    if not _cdp_reachable(timeout=3.0):
        raise RuntimeError("CDP at 127.0.0.1:9222 not reachable — skipping browser-harness")

    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local/bin'}:{env.get('PATH', '')}"
    env["BU_CDP_URL"] = "http://127.0.0.1:9222"

    script = _BROWSER_HARNESS_SCRIPT.replace("__DOMAIN__", domain)

    result = subprocess.run(
        ["browser-harness", "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(f"browser-harness failed: {result.stderr.strip()}")

    output = result.stdout.strip()
    if not output:
        raise RuntimeError("browser-harness produced no output — Edge may not be running with --remote-debugging-port=9222")

    try:
        cookies = json.loads(output)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"browser-harness returned unexpected output: {output!r}") from e

    if not cookies:
        raise RuntimeError("No Brighton cookies found — make sure you are logged into Blackboard in Edge")

    return cookies


def _find_powershell() -> str:
    """Return the path to powershell.exe."""
    candidates = [
        "powershell.exe",
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
    ]
    return next(
        (p for p in candidates if Path(p).exists() or p == "powershell.exe"),
        "powershell.exe",
    )


def _extract_via_cdp(domain: str) -> dict:
    """
    Extract cookies via Chrome DevTools Protocol (bypasses App-Bound Encryption).

    Kills any running Edge processes first (releases profile lock), then launches
    Edge hidden with the real user profile and --remote-debugging-port=9222.
    A Windows Python CDP client connects and calls Network.getAllCookies.
    Edge is killed in a PowerShell finally block regardless of outcome.

    Raises RuntimeError on any failure.
    """
    Path(_CDP_SCRIPT_WSL).write_text(_CDP_WIN_SCRIPT)

    powershell = _find_powershell()
    ps_cmd = _CDP_PS_CMD.replace("{domain}", domain)

    result = subprocess.run(
        [powershell, "-Command", ps_cmd],
        capture_output=True,
        text=True,
        timeout=90,  # Edge start (~8s) + CDP poll (20s) + extraction
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"CDP extraction failed.\n{result.stderr.strip()}"
        )

    output = result.stdout.strip()
    if not output:
        raise RuntimeError(
            "CDP script produced no output — Edge may have failed to start or cookies are empty"
        )

    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"CDP script returned unexpected output: {output!r}") from e


def extract_bb_cookies(force_refresh: bool = False) -> dict:
    """
    Extract Edge session cookies for BB_BASE_URL.
    Tries methods in order:
      1. Direct WSL2 CDP (websocket-client, fastest, no daemon)
      2. browser-harness via 127.0.0.1:9222 (only if CDP reachable)
      3. Chrome DevTools Protocol via Windows PowerShell (kills/restarts Edge)
      4. Manually exported Cookie-Editor JSON
      5. browser_cookie3 via Windows Python (legacy, broken on Edge 127+)
    Caches result to COOKIE_CACHE for 1 hour. Returns dict of {name: value}.
    Raises RuntimeError if all methods fail.
    """
    cache = Path(COOKIE_CACHE)
    if not force_refresh and cache.exists():
        age = time.time() - cache.stat().st_mtime
        if age < 3600:
            try:
                return json.loads(cache.read_text())
            except (json.JSONDecodeError, OSError):
                pass  # fall through to re-extraction

    domain = urlparse(BB_BASE_URL).netloc  # studentcentral.brighton.ac.uk

    # --- Method 1: Direct WSL2 CDP via websocket-client (fastest, no daemon overhead) ---
    try:
        print("    [wsl-cdp] Extracting cookies directly via CDP WebSocket…")
        cookies = _extract_via_wsl_cdp(domain)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(cookies))
        return cookies
    except RuntimeError as e:
        print(f"    [wsl-cdp] Failed: {e}")

    # --- Method 2: browser-harness via WSL2 CDP (127.0.0.1:9222) ---
    try:
        print("    [browser-harness] Extracting cookies via browser-harness…")
        cookies = _extract_via_browser_harness(domain)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(cookies))
        return cookies
    except RuntimeError as e:
        print(f"    [browser-harness] Failed: {e}")
        print("    [browser-harness] Falling back to Windows CDP…")

    # --- Method 3: Chrome DevTools Protocol via Windows PowerShell ---
    try:
        print("    [cdp] Extracting cookies via Chrome DevTools Protocol…")
        cookies = _extract_via_cdp(domain)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(cookies))
        return cookies
    except RuntimeError as e:
        print(f"    [cdp] CDP failed: {e}")
        print("    [cdp] Falling back to alternative methods…")

    # --- Method 4: Manually exported Cookie-Editor JSON ---
    _manual_paths = [_WINDOWS_MANUAL_EXPORT_WSL] + _WINDOWS_MANUAL_EXPORT_EXTRA_WSL
    manual = next((Path(p) for p in _manual_paths if Path(p).exists()), None)
    if manual is not None:
        print(f"    [cookie-editor] Reading from {manual}")
        try:
            raw = json.loads(manual.read_text())
            if isinstance(raw, list):
                cookies = {c["name"]: c["value"] for c in raw if "name" in c and "value" in c}
            else:
                cookies = raw
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(cookies))
            return cookies
        except (json.JSONDecodeError, OSError, KeyError) as e:
            print(f"    [cookie-editor] Skipping malformed export file: {e}")
            # fall through to browser_cookie3

    # --- Method 5: browser_cookie3 via Windows Python (legacy, broken on Edge 127+) ---
    powershell = _find_powershell()
    ps_command = f"python -c '{_WINDOWS_SCRIPT}' {domain}"
    result = subprocess.run(
        [powershell, "-Command", ps_command],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        ps_command_py = f"py -3 -c '{_WINDOWS_SCRIPT}' {domain}"
        result = subprocess.run(
            [powershell, "-Command", ps_command_py],
            capture_output=True, text=True, timeout=30,
        )

    if result.returncode != 0:
        raise RuntimeError(
            f"Cookie extraction failed. All methods exhausted.\n"
            f"CDP failed (see above). browser_cookie3 error: {result.stderr.strip()}\n"
            f"Workaround: export cookies manually with Cookie-Editor and save to "
            f"{_WINDOWS_MANUAL_EXPORT}"
        )

    cookies = json.loads(result.stdout.strip())
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(cookies))
    return cookies
