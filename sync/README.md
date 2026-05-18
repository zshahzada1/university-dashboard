# university-blackboard-sync

Syncs files from Blackboard Ultra to a local folder on WSL2. Extracts session cookies from a running Edge instance via Chrome DevTools Protocol (CDP) — no password needed after you log in once.

## How it works

1. Reads Edge's session cookies via CDP (Edge must be open and logged into Blackboard)
2. Walks the Blackboard content tree for each module using the REST API
3. Downloads any files not already present locally
4. Skips files that already exist — safe to re-run at any time

## Prerequisites

| Requirement | Notes |
|---|---|
| WSL2 on Windows 10/11 | Tested on Ubuntu |
| Microsoft Edge | Must be open and logged into Blackboard |
| Python 3.8+ in WSL | `python3 --version` |
| Python 3.x in Windows | Needed for CDP cookie extraction — install from [python.org](https://python.org) |
| `requests` + `websocket-client` in **Windows** Python | `pip install requests websocket-client` |

## Installation

```bash
git clone https://github.com/zshahzada1/university-blackboard-sync.git
cd university-blackboard-sync
pip3 install -r requirements.txt
```

## Configuration

By default the script syncs to `~/University/<MODULE_CODE>/`. To change this, set environment variables before running:

```bash
export BB_LOCAL_ROOT="$HOME/Documents/University"   # where to save files
export BB_COOKIE_CACHE="$HOME/.cache/bb_sync/cookies.json"  # cookie cache location
export BB_BASE_URL="https://studentcentral.brighton.ac.uk"  # your Blackboard URL
```

To change **which modules** are synced by default, edit `SYNC_MODULES` in `scripts/bb_sync/config.py`:

```python
SYNC_MODULES = {"FA565", "FN585", "FA583"}
```

## Usage

**Sync specific modules (recommended):**
```bash
./sync.sh --modules FA565 FN585 FA583
```

**Sync all modules in the allowlist:**
```bash
./sync.sh
```

**Force re-extract cookies (if sync fails with auth errors):**
```bash
./sync.sh --refresh-cookies --modules FA565 FN585 FA583
```

**List all enrolled courses:**
```bash
./sync.sh --list-courses
```

### Running without sync.sh

```bash
cd scripts && python3 -m bb_sync --modules FA565 FN585 FA583
```

## Troubleshooting

**`CDP not ready within 20s`**
Edge didn't start with the debug port. Make sure Edge is running, then try again. The script briefly closes and restarts Edge — don't click anything during that window.

**`No Python found in Windows PATH`**
Install Python from [python.org](https://python.org) and make sure it's on the Windows PATH. In a Windows terminal: `python --version`

**`pip install requests websocket-client` (in Windows Python)**
The CDP extraction script runs on Windows Python. Open PowerShell and run:
```powershell
pip install requests websocket-client
```

**Auth errors after a long time**
Blackboard sessions expire. Open Edge, log in to Blackboard, then re-run with `--refresh-cookies`.

## File layout

```
scripts/bb_sync/
  __main__.py        — CLI entry point
  bb_client.py       — Blackboard REST API client
  config.py          — URLs, paths, module allowlist
  cookie_extractor.py — Edge CDP cookie extraction
  syncer.py          — content tree walker + file downloader
  requirements.txt   — Python dependencies
  test_*.py          — unit tests
```

## Running tests

```bash
cd scripts/bb_sync && python3 -m unittest discover -v
```
