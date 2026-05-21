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
  run.sh        — Mac / Linux / WSL2 launcher
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
| `BBSYNC_PYTHON` | set by `start.py` | Python used for the bb_sync subprocess |
| `BBSYNC_SCRIPTS_DIR` | `sync/scripts/` | Working directory for bb_sync |
| `BB_BASE_URL` | `https://studentcentral.brighton.ac.uk` | Blackboard instance URL |
