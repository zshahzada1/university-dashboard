# Uni Hub Dashboard

Local study hub for tracking grades, deadlines, files, tasks, notes, and topic confidence across all Blackboard modules.

## Architecture

```
dashboard/
  backend/      — FastAPI (Python 3.12), port 8765
  frontend/     — React + TypeScript + Vite, port 5173 (dev)
  sync/         — bb_sync CLI: Blackboard file + grade sync
  run.sh        — starts both processes
```

The backend serves the built frontend at `http://localhost:8765` in production. In dev mode both servers run separately and the frontend proxies API calls to the backend.

## Running

**Production (one process):**
```bash
./run.sh
# open http://localhost:8765
```

**Development (hot-reload):**
```bash
./run.sh dev
# frontend: http://localhost:5173
# backend:  http://localhost:8765
```

## Features

| Section | Description |
|---|---|
| Grades | Live grade view with module breakdowns, weighted averages, and remaining-mark projections |
| Files | File tree browser for all synced Blackboard content |
| Assignments | Deadline tracker with status and links to grades |
| Tasks | Personal to-do list per module |
| Events | Calendar of upcoming events and deadlines |
| Notes | Per-module markdown notes |
| Topics | Confidence tracker for syllabus topics |
| Search | Full-text search across files and notes |
| Sync | In-browser trigger for Blackboard file + grade sync |

## Blackboard Sync

Files and grades are synced from Blackboard via `sync/`. Edge must be open and logged in — no password is ever stored; cookies are extracted live via CDP.

**Sync files + grades (from the dashboard UI):** use the Sync page.

**Sync from the terminal:**
```bash
cd sync && bash sync.sh --modules FA565 FN585 FA583
```

**Grades only (all modules):**
```bash
cd sync && bash sync.sh --grades
```

**Force cookie refresh (if auth fails):**
```bash
cd sync && bash sync.sh --refresh-cookies --modules FA565 FN585 FA583
```

See [`sync/README.md`](sync/README.md) for full sync documentation.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `UNI_DIR` | `~/University` | Root folder for synced course files |
| `UNI_DATA_DIR` | `backend/data/` | JSON data directory |
| `BBSYNC_PYTHON` | `sync/scripts/.venv/bin/python` | Python interpreter for bb_sync |
| `BBSYNC_SCRIPTS_DIR` | `sync/scripts/` | Working directory for bb_sync |

## Setup

**Backend:**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

**Frontend:**
```bash
cd frontend
npm install
```

**bb_sync:**
```bash
cd sync/scripts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
