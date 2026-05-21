# One-Click Packaging Design

**Date:** 2026-05-21  
**Status:** Approved

## Goal

Make the dashboard installable and runnable by friends on Windows, Mac, and Linux/WSL2 with minimal steps — no manual venv setup, no Node.js, no understanding of Python packaging.

## Setup Flow (for a friend)

```
# Step 1 — install uv (one command, ~30 seconds)
Mac/Linux:  curl -LsSf https://astral.sh/uv/install.sh | sh
Windows:    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Step 2 — clone
git clone https://github.com/zshahzada1/university-dashboard.git
cd university-dashboard

# Step 3 — run
uv run start.py          # Mac/Linux/WSL2
run.bat                  # Windows (double-click or terminal)
```

uv reads the PEP 723 inline dependency list from `start.py`, creates a managed venv, installs all deps, and starts the server. No pip, no venv, no Node.

## Architecture

```
dashboard/
  start.py                       ← entry point (uv inline script)
  run.sh                         ← thin wrapper: uv run start.py
  run.bat                        ← Windows: uv run start.py
  pyproject.toml                 ← root-level, all Python deps
  frontend/dist/                 ← committed; friends skip Node entirely
  sync/scripts/bb_sync/
    browser_launcher.py          ← OS detection + browser launch
    cookie_extractor.py          ← CDP extraction (already simplified)
```

## `start.py` Startup Sequence

1. Check if a CDP debug port is already reachable on `127.0.0.1:9222` or `:9223`
2. If not reachable: run the browser wizard (see below)
3. Set `BBSYNC_PYTHON=sys.executable` — sync module reuses this managed venv
4. Set `BBSYNC_SCRIPTS_DIR` to `sync/scripts/`
5. Add `backend/` to `sys.path` so uvicorn can import `app.main`
6. Start uvicorn on `127.0.0.1:8765`

### PEP 723 inline metadata

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
```

## Browser Wizard (`browser_launcher.py`)

Triggered from `start.py` when no CDP port is open.

### OS Detection

| OS | Detection method |
|---|---|
| WSL2 | `platform.system() == "Linux"` and `/proc/version` contains `"microsoft"` |
| Windows native | `platform.system() == "Windows"` |
| Mac | `platform.system() == "Darwin"` |
| Linux | `platform.system() == "Linux"` (non-WSL) |

### Browser Search Paths

**WSL2** — checks `/mnt/c/...` Windows paths (WSL2 can execute Windows binaries directly):
- `/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`
- `/mnt/c/Program Files/Google/Chrome/Application/chrome.exe`
- `/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe`

**Windows native** — same paths under `C:\...`

**Mac** — checks `/Applications/`:
- `Google Chrome.app/Contents/MacOS/Google Chrome`
- `Microsoft Edge.app/Contents/MacOS/Microsoft Edge`
- `Chromium.app/Contents/MacOS/Chromium`

**Linux** — `shutil.which()` for: `google-chrome`, `chromium-browser`, `chromium`, `microsoft-edge`

### Wizard Terminal UX

```
No browser debug port found. Let's open one for you.

Detected browsers:
  [1] Google Chrome
  [2] Microsoft Edge

Pick a browser [1]: _
Launching Google Chrome with remote debugging...

Log in to Blackboard in the browser window, then press Enter to continue: _

Connected. Starting server → http://localhost:8765
```

If no browser is detected, print a clear manual instruction and exit cleanly (don't start the server).

### Launch Method

All platforms: `subprocess.Popen([path, "--remote-debugging-port=9222", "--no-first-run", "--no-default-browser-check", "about:blank"])` — WSL2 runs the Windows `.exe` directly via the `/mnt/c/...` path (no cmd.exe needed).

After launch, poll `127.0.0.1:9222` for up to 20 seconds (0.5s intervals) before prompting the user to press Enter, so the wait doesn't feel broken.

## Root `pyproject.toml`

Consolidates all runtime deps in one place for uv. The existing `backend/pyproject.toml` and `sync/scripts/bb_sync/requirements.txt` stay for dev/test use but are no longer needed to run the app.

## Frontend Distribution

- Remove `frontend/dist/` from `.gitignore`
- Build `frontend/dist/` and commit it
- Friends clone and run immediately — no Node.js required
- `main.py` already serves `frontend/dist/` as static files when the directory exists

## Files Changed

| File | Action |
|---|---|
| `start.py` | Create — uv inline script, browser wizard, uvicorn launch |
| `run.sh` | Update — call `uv run start.py` instead of activating venv |
| `run.bat` | Create — `@uv run start.py` for Windows |
| `pyproject.toml` (root) | Create — all runtime deps |
| `sync/scripts/bb_sync/browser_launcher.py` | Create — OS detection + launch |
| `.gitignore` | Update — remove `frontend/dist/` exclusion |
| `frontend/dist/` | Build and commit |
| `README.md` | Rewrite — 3-step setup, Blackboard setup section |
| `sync/README.md` | Update — note that venv setup is no longer required |

## Out of Scope

- Dev workflow (hot-reload) — `run.sh dev` continues to work with the existing backend venv
- Data personalisation — friends' modules/assignments are seeded from defaults on first run; they customise via the UI or by syncing their own Blackboard account
- Automatic Blackboard login — cookie extraction requires the user to be logged in; this cannot be automated
