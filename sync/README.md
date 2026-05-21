# bb_sync

Syncs files and grades from Blackboard Ultra to a local folder on WSL2. Extracts session cookies from a running Edge instance via Chrome DevTools Protocol (CDP) — no password needed after you log in once.

The sync module lives at `sync/` inside the dashboard repo and is invoked by the dashboard backend's Sync page as well as directly from the terminal.

## How it works

1. Reads Edge's session cookies via CDP (Edge must be open and logged into Blackboard)
2. Walks the Blackboard content tree for each module using the REST API
3. Downloads any files not already present locally (streamed to a `.tmp` file, renamed on completion)
4. Skips files that already exist — safe to re-run at any time
5. Syncs grade columns for all modules and writes `backend/data/grades.json`

## Prerequisites

| Requirement | Notes |
|---|---|
| uv | Installed via the dashboard Quick Start — handles Python and all deps |
| Chrome or Edge | Must be open and logged into Blackboard |

No manual venv setup needed — `uv run start.py` handles everything automatically.

## Manual venv (development / tests only)

```bash
cd sync/scripts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Settings are read from environment variables with defaults in `scripts/bb_sync/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `BB_BASE_URL` | `https://studentcentral.brighton.ac.uk` | Blackboard instance URL |
| `BB_LOCAL_ROOT` | `~/University` | Root folder where course subfolders are created |
| `BB_COOKIE_CACHE` | `~/.cache/bb_sync/cookies.json` | Cookie cache (valid 1 hour) |
| `BB_ASSESSMENTS_PATH` | `dashboard/backend/data/assessments.json` | Assessment config for grade sync |
| `BB_GRADES_PATH` | `dashboard/backend/data/grades.json` | Grade sync output |

To change which modules are synced by default, edit `SYNC_MODULES` in `scripts/bb_sync/config.py`:

```python
SYNC_MODULES = {"FA565", "FN585", "FA583"}
```

## Usage

**Sync specific modules (files + grades):**
```bash
bash sync.sh --modules FA565 FN585 FA583
```

**Sync all modules in the allowlist:**
```bash
bash sync.sh
```

**Grades only (all modules, no file download):**
```bash
bash sync.sh --grades
```

**Force re-extract cookies (if sync fails with auth errors):**
```bash
bash sync.sh --refresh-cookies --modules FA565 FN585 FA583
```

**List enrolled courses as JSON:**
```bash
bash sync.sh --list-courses
```

**Without sync.sh:**
```bash
cd scripts && python3 -m bb_sync --modules FA565 FN585 FA583
```

## File layout

```
sync/
  sync.sh                    — shell wrapper (activates .venv, runs bb_sync)
  requirements.txt           — top-level deps (mirrors scripts/bb_sync/requirements.txt)
  scripts/
    bb_sync/
      __main__.py            — CLI entry point, argument parsing
      bb_client.py           — Blackboard REST API client (persistent requests.Session)
      config.py              — URLs, paths, module allowlist
      cookie_extractor.py    — Edge CDP cookie extraction (4 fallback methods)
      grades.py              — GradeSyncer: fetches and writes grade columns
      syncer.py              — content tree walker + atomic file downloader
      test_bb_client.py      — unit tests for BlackboardClient
      test_syncer.py         — unit tests for Syncer and download helpers
      requirements.txt       — Python dependencies
```

## Running tests

```bash
cd sync/scripts/bb_sync
python3 -m unittest discover -v
```

## Troubleshooting

**`Could not connect to a browser debug port` / cookie extraction fails**
Chrome or Edge must be running with `--remote-debugging-port=9222`. The easiest fix is to close the browser and re-run `uv run start.py` — the startup wizard will relaunch it correctly. Or start the browser manually:
```bash
# Windows / WSL2
msedge.exe --remote-debugging-port=9222
# Mac
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```
Then log in to Blackboard and re-run with `--refresh-cookies`.

**Auth errors after a long session**
Blackboard sessions expire. Open Edge, log in to Blackboard, then:
```bash
bash sync.sh --refresh-cookies --modules FA565 FN585 FA583
```

**FA565 has few downloaded files**
Expected — most FA565 content is inline HTML rather than file attachments. The syncer saves these as `.html` files and downloads any embedded attachment links it finds inside them.
