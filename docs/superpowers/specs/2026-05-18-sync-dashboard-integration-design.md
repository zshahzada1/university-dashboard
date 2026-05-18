# Sync + Dashboard Integration Design

**Date:** 2026-05-18  
**Status:** Approved

## Overview

Extend the university dashboard with:
1. A **Sync page** — fetch live module list from Blackboard, choose what to sync, trigger and watch the sync in real time
2. A **Files page** — folder-tree browser of `~/University/` content  
3. **GitHub push** — bb_sync_repo to existing remote; dashboard to a new repo

The sync script (`bb_sync`) already handles all the heavy lifting. The dashboard wraps it with a UI.

---

## 1. GitHub Push

- **bb_sync_repo** (`/home/zozo/bb_sync_repo`): already has remote `https://github.com/zshahzada1/university-blackboard-sync.git`. Commit current changes and push.
- **Dashboard** (`/home/zozo/University/dashboard`): create new GitHub repo `university-dashboard`, set as origin, push `main`.

---

## 2. Backend: Sync API

### Settings

Add to `app/settings.py`:
- `bbsync_python: Path` — path to the venv Python that runs `bb_sync`. Default: `~/bb_sync_repo/scripts/.venv/bin/python`. Override with `BBSYNC_PYTHON` env var.
- `bbsync_scripts_dir: Path` — the directory passed as `cwd` when running bb_sync (`~/bb_sync_repo/scripts`). Override with `BBSYNC_SCRIPTS_DIR`.

### `GET /api/sync/courses`

Runs `bbsync_python -m bb_sync --list-courses` as a subprocess with `cwd=bbsync_scripts_dir`. Captures stdout (JSON array `[{id, name, code}]`), stderr is discarded. Returns the parsed JSON. Times out after 30 s. Returns `500` with error message if the subprocess fails.

### `POST /api/sync/run`

**Request body:**
```json
{
  "modules": ["FA565", "FN585"],
  "mode": "all" | "files" | "grades"
}
```

Builds the `bb_sync` command:
- `mode=grades` → `--grades` flag only (no `--modules` needed — grades always sync all)
- `mode=files` or `mode=all` → `--modules <selected>` (omit `--modules` if all modules selected or none specified)
- Grades are always synced during a normal (all/files) run anyway, so no extra flag needed

Streams stdout+stderr merged via `asyncio.create_subprocess_exec`. Returns `StreamingResponse` with `media_type="text/event-stream"` (SSE). Each line of output becomes:
```
data: <line text>\n\n
```
On process exit, emits:
```
data: __exit__:<returncode>\n\n
```

Only one sync may run at a time. A module-level boolean flag (`_sync_running`) in the route module tracks this. Set to `True` at subprocess start, `False` in a `finally` block. If already `True`, return `409 Conflict`.

---

## 3. Backend: File Tree API

### `GET /api/files/tree`

Scans `settings.university_dir` (`~/University/`) recursively. 

**Excluded at top level:** `dashboard/`, `docs/`, `CLAUDE.md`, `GEMINI.md`, and any hidden files/dirs (starting with `.`).

Returns a nested structure:
```json
[
  {
    "name": "FA565",
    "type": "dir",
    "children": [
      {
        "name": "Week 1 - Introduction",
        "type": "dir", 
        "children": [
          {
            "name": "lecture.pdf",
            "type": "file",
            "size": 204800,
            "rel_path": "FA565/Week 1 - Introduction/lecture.pdf"
          }
        ]
      }
    ]
  }
]
```

Sorted: directories before files, then alphabetically. Max depth: 5 levels (prevents runaway traversal). Empty directories are included (shows structure even if nothing downloaded yet).

New route file: `app/routes/sync.py` (for sync endpoints) and file tree added to `app/routes/files.py`.

---

## 4. Frontend: Sync Page

**Route:** `/sync` — new nav entry "Sync" in sidebar.

**Layout (top to bottom):**
1. **Module list** — loads on mount via `GET /api/sync/courses`. Shows spinner while loading. Each module: checkbox + code + name. "Select all / none" toggle at top.
2. **Mode selector** — radio buttons: `Files + Grades` (default) / `Files only` / `Grades only`
3. **Sync button** — disabled while loading courses or while a sync is running. Label: "Sync" / "Syncing…"
4. **Terminal panel** — hidden until sync starts. Fixed-height (~300px) scrollable div with monospace font, dark background. Auto-scrolls to bottom. Shows each SSE line as it arrives. On `__exit__:0` appends a green "Done." line; on non-zero exit appends a red "Sync failed (exit N)." line.

**API additions to `api.ts`:**
- `api.syncCourses()` → `GET /api/sync/courses` → `{id, name, code}[]`
- `api.syncRun(modules, mode)` → `POST /api/sync/run` using `fetch`. Since `EventSource` is GET-only, reads `response.body` as a `ReadableStream` with a `TextDecoder`. Caller passes a callback `onLine(line: string)` called for each `data: …` SSE line received.

---

## 5. Frontend: Files Page

**Route:** `/files` — new nav entry "Files" in sidebar.

**Layout:** Single-column folder tree. Each row is a node:
- **Directory node:** chevron (▶/▼) + folder icon + name + file count badge. Click toggles expand/collapse. Top-level module dirs are expanded by default; subdirs collapsed.
- **File node:** file icon + name + size (human-readable). Click calls `POST /api/open` with `rel_path`.

State: expand/collapse tracked in component state (not persisted). All top-level dirs start expanded.

New component: `FileBrowser.tsx` is already in the codebase (currently used per-topic) — the new Files page uses a new `FileTree.tsx` component that handles nested recursive rendering.

---

## 6. Nav Updates

Add two entries to the sidebar navigation. Current order: Home → Grades → Deadlines → Planner → Resources. New order:

Home → Grades → Deadlines → Planner → Resources → **Files** → **Sync**

---

## Error Handling

- **Courses fetch fails** (Edge not open, cookies expired): show inline error on Sync page with message from API — "Could not connect to Blackboard. Make sure Edge is open and you're logged in."
- **Sync fails mid-run**: terminal shows the error output; `__exit__:N` triggers the red failure line. User can re-run.
- **File tree empty dir**: shown with grayed-out "empty" label so user knows a module exists but has no downloads yet.

---

## Out of Scope

- Scheduling / auto-sync on a timer
- Conflict resolution or file deletion
- Multi-user / auth
- Deploying the dashboard to a public host
