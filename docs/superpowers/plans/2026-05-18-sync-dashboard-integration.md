# Sync + Dashboard Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a live Sync page and folder-tree Files page to the dashboard, backed by new FastAPI endpoints that run `bb_sync` as a subprocess and scan `~/University/`.

**Architecture:** Two new FastAPI route modules (`sync.py` adds `/api/sync/courses` + `/api/sync/run`; `files.py` gets a new `/api/files/tree` endpoint). The frontend gains a `FileTree` component, a `Files` page, and a `Sync` page wired into the existing hash-router and sidebar nav.

**Tech Stack:** Python 3.12 + FastAPI + asyncio subprocess (backend); React 19 + TypeScript + fetch ReadableStream SSE (frontend); pytest + vitest (tests); gh CLI (GitHub).

---

## File Map

**Create:**
- `backend/app/routes/sync.py` — `/api/sync/courses` and `/api/sync/run` endpoints
- `backend/tests/test_sync_route.py` — tests for sync routes
- `frontend/src/components/FileTree.tsx` — recursive tree node component
- `frontend/src/components/FileTree.module.css`
- `frontend/src/routes/Files.tsx` — Files page
- `frontend/src/routes/Files.module.css`
- `frontend/src/routes/Sync.tsx` — Sync page
- `frontend/src/routes/Sync.module.css`

**Modify:**
- `backend/app/settings.py` — add `bbsync_python` + `bbsync_scripts_dir` fields
- `backend/app/routes/files.py` — add `GET /api/files/tree`
- `backend/tests/test_files.py` — add tree test
- `backend/app/main.py` — register `sync` router
- `frontend/src/lib/types.ts` — add `SyncCourse`, `FileNode`, `DirNode`, `TreeNode`
- `frontend/src/lib/api.ts` — add `syncCourses`, `syncRun`, `fileTree`
- `frontend/src/components/Layout.tsx` — add Files + Sync nav entries
- `frontend/src/App.tsx` — add `#/files` and `#/sync` routes

---

## Task 0: Commit and push bb_sync_repo to GitHub

**Files:** `/home/zozo/bb_sync_repo` (6 modified files)

- [ ] **Step 1: Stage and commit all changes**

```bash
cd /home/zozo/bb_sync_repo
git add scripts/bb_sync/__main__.py scripts/bb_sync/bb_client.py \
        scripts/bb_sync/cookie_extractor.py scripts/bb_sync/syncer.py \
        scripts/bb_sync/test_syncer.py sync.sh
git commit -m "feat: direct WSL2 CDP extraction, grade sync fixes, displayGrade score mapping"
```

- [ ] **Step 2: Push to origin**

```bash
git push origin HEAD
```

Expected: push succeeds to `https://github.com/zshahzada1/university-blackboard-sync.git`.

---

## Task 1: Extend Settings with bbsync paths

**Files:**
- Modify: `backend/app/settings.py`

- [ ] **Step 1: Update `settings.py`**

Replace the entire file with:

```python
from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    university_dir: Path
    data_dir: Path
    bbsync_python: Path
    bbsync_scripts_dir: Path

    @property
    def modules_path(self): return self.data_dir / "modules.json"
    @property
    def topics_path(self):  return self.data_dir / "topics.json"
    @property
    def assignments_path(self): return self.data_dir / "assignments.json"
    @property
    def tasks_path(self): return self.data_dir / "tasks.json"
    @property
    def events_path(self): return self.data_dir / "events.json"
    @property
    def state_path(self): return self.data_dir / "state.json"
    @property
    def notes_dir(self): return self.data_dir / "notes"
    @property
    def assessments_path(self): return self.data_dir / "assessments.json"
    @property
    def grades_path(self): return self.data_dir / "grades.json"

def load_settings() -> Settings:
    here = Path(__file__).resolve().parents[1]  # backend/
    home = Path.home()
    return Settings(
        university_dir=Path(os.environ.get("UNI_DIR", str(home / "University"))),
        data_dir=Path(os.environ.get("UNI_DATA_DIR", str(here / "data"))),
        bbsync_python=Path(os.environ.get(
            "BBSYNC_PYTHON",
            str(home / "bb_sync_repo" / "scripts" / ".venv" / "bin" / "python"),
        )),
        bbsync_scripts_dir=Path(os.environ.get(
            "BBSYNC_SCRIPTS_DIR",
            str(home / "bb_sync_repo" / "scripts"),
        )),
    )
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest -x -q
```

Expected: all tests pass (settings change is additive; existing tests don't touch new fields).

- [ ] **Step 3: Commit**

```bash
cd /home/zozo/University/dashboard
git add backend/app/settings.py
git commit -m "feat: add bbsync_python + bbsync_scripts_dir to Settings"
```

---

## Task 2: Backend sync routes

**Files:**
- Create: `backend/app/routes/sync.py`
- Create: `backend/tests/test_sync_route.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_sync_route.py`:

```python
from __future__ import annotations
import json
import subprocess
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main
import app.routes.sync as sync_module


def _make_completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_courses_success():
    courses = [{"id": "_1_1", "name": "FA565 Business Ethics", "code": "FA565"}]
    with patch("app.routes.sync.subprocess.run", return_value=_make_completed(json.dumps(courses))):
        with TestClient(app.main.app) as client:
            r = client.get("/api/sync/courses")
    assert r.status_code == 200
    assert r.json()[0]["code"] == "FA565"


def test_courses_subprocess_failure():
    err = _make_completed("", returncode=1)
    err = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="CDP failed")
    with patch("app.routes.sync.subprocess.run", return_value=err):
        with TestClient(app.main.app) as client:
            r = client.get("/api/sync/courses")
    assert r.status_code == 500
    assert "CDP failed" in r.json()["detail"]


def test_sync_run_conflict():
    sync_module._sync_running = True
    try:
        with TestClient(app.main.app) as client:
            r = client.post("/api/sync/run", json={"modules": ["FA565"], "mode": "all"})
        assert r.status_code == 409
    finally:
        sync_module._sync_running = False


```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest tests/test_sync_route.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `app.routes.sync` does not exist yet.

- [ ] **Step 3: Create `backend/app/routes/sync.py`**

```python
from __future__ import annotations
import asyncio
import json
import subprocess
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.settings import load_settings

router = APIRouter(prefix="/api/sync", tags=["sync"])

_sync_running = False


class SyncRequest(BaseModel):
    modules: list[str]
    mode: str  # "all" | "files" | "grades"


@router.get("/courses")
def get_courses():
    s = load_settings()
    try:
        result = subprocess.run(
            [str(s.bbsync_python), "-m", "bb_sync", "--list-courses"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(s.bbsync_scripts_dir),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(500, detail="Course fetch timed out (30s). Is Edge open and logged in?")
    if result.returncode != 0:
        msg = result.stderr.strip() or "bb_sync --list-courses failed"
        raise HTTPException(500, detail=msg)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise HTTPException(500, detail=f"Invalid JSON from bb_sync: {e}")


@router.post("/run")
async def run_sync(body: SyncRequest):
    global _sync_running
    if _sync_running:
        raise HTTPException(409, detail="Sync already running")

    s = load_settings()
    args = [str(s.bbsync_python), "-m", "bb_sync"]

    if body.mode == "grades":
        args.append("--grades")
    else:
        if body.modules:
            args.extend(["--modules"] + body.modules)

    async def generate():
        global _sync_running
        _sync_running = True
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(s.bbsync_scripts_dir),
            )
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield f"data: {line.decode().rstrip()}\n\n"
            await proc.wait()
            yield f"data: __exit__:{proc.returncode}\n\n"
        finally:
            _sync_running = False

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest tests/test_sync_route.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd /home/zozo/University/dashboard
git add backend/app/routes/sync.py backend/tests/test_sync_route.py
git commit -m "feat: add /api/sync/courses and /api/sync/run endpoints"
```

---

## Task 3: File tree endpoint

**Files:**
- Modify: `backend/app/routes/files.py`
- Modify: `backend/tests/test_files.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_files.py`:

```python
import os
from pathlib import Path
from fastapi.testclient import TestClient
import app.main


def test_file_tree_returns_structure():
    uni = Path(os.environ["UNI_DIR"])
    (uni / "FA565" / "Week 1 - Intro").mkdir(parents=True, exist_ok=True)
    (uni / "FA565" / "Week 1 - Intro" / "slides.pdf").write_bytes(b"%PDF-1.4")
    (uni / "dashboard").mkdir(exist_ok=True)

    with TestClient(app.main.app) as client:
        r = client.get("/api/files/tree")
    assert r.status_code == 200
    tree = r.json()
    names = [n["name"] for n in tree]
    assert "FA565" in names
    assert "dashboard" not in names

    fa565 = next(n for n in tree if n["name"] == "FA565")
    assert fa565["type"] == "dir"
    week1 = fa565["children"][0]
    assert week1["name"] == "Week 1 - Intro"
    slide = week1["children"][0]
    assert slide["name"] == "slides.pdf"
    assert slide["type"] == "file"
    assert slide["size"] > 0
    assert slide["rel_path"] == "FA565/Week 1 - Intro/slides.pdf"


def test_file_tree_excludes_hidden_dirs():
    uni = Path(os.environ["UNI_DIR"])
    (uni / ".hidden").mkdir(exist_ok=True)
    (uni / ".hidden" / "secret.txt").write_text("x")

    with TestClient(app.main.app) as client:
        r = client.get("/api/files/tree")
    names = [n["name"] for n in r.json()]
    assert ".hidden" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest tests/test_files.py::test_file_tree_returns_structure tests/test_files.py::test_file_tree_excludes_hidden_dirs -v
```

Expected: FAIL with `404` or route not found.

- [ ] **Step 3: Add `build_tree` function and `/tree` endpoint to `backend/app/routes/files.py`**

Replace the entire file with:

```python
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.services.store import JsonStore
from app.settings import load_settings

router = APIRouter(prefix="/api/files", tags=["files"])

_TREE_SKIP = {"dashboard", "docs", ".git", "__pycache__", "node_modules"}
_TREE_SKIP_FILES = {"CLAUDE.md", "GEMINI.md"}


def _build_tree(path: Path, root: Path, depth: int = 0, max_depth: int = 5) -> list[dict]:
    if depth >= max_depth:
        return []
    dirs: list[Path] = []
    files: list[Path] = []
    try:
        for child in sorted(path.iterdir()):
            if child.name.startswith("."):
                continue
            if child.is_dir():
                if child.name not in _TREE_SKIP:
                    dirs.append(child)
            elif child.is_file() and child.name not in _TREE_SKIP_FILES:
                files.append(child)
    except PermissionError:
        return []
    items: list[dict] = []
    for d in dirs:
        items.append({
            "name": d.name,
            "type": "dir",
            "children": _build_tree(d, root, depth + 1, max_depth),
        })
    for f in files:
        items.append({
            "name": f.name,
            "type": "file",
            "size": f.stat().st_size,
            "rel_path": str(f.relative_to(root)),
        })
    return items


@router.get("/tree")
def file_tree():
    s = load_settings()
    if not s.university_dir.exists():
        return []
    return _build_tree(s.university_dir, s.university_dir)


@router.get("")
def list_files(module: str, topic_id: str):
    s = load_settings()
    mods = JsonStore(s.modules_path, default=[]).read()
    mod = next((m for m in mods if m["code"] == module), None)
    if not mod:
        raise HTTPException(404, "unknown module")
    topics = JsonStore(s.topics_path, default={}).read().get(module, [])
    t = next((x for x in topics if x["id"] == topic_id), None)
    if not t:
        raise HTTPException(404, "unknown topic")
    folder: Path = s.university_dir / mod["folder"] / t["folder"]
    if not folder.exists():
        return []
    out = []
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            rel = p.relative_to(s.university_dir)
            out.append({"name": p.name, "rel_path": str(rel), "size": p.stat().st_size})
    return out
```

- [ ] **Step 4: Run all file tests**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest tests/test_files.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full backend test suite**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest -x -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /home/zozo/University/dashboard
git add backend/app/routes/files.py backend/tests/test_files.py
git commit -m "feat: add GET /api/files/tree endpoint"
```

---

## Task 4: Register sync router in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add sync router import and registration**

In `backend/app/main.py`, add `sync` to the imports and `app.include_router` calls:

```python
from app.routes import modules, topics, assignments, tasks, events, notes, files, search, open_file, state, grades, sync
```

And add after the other `include_router` calls:

```python
app.include_router(sync.router)
```

- [ ] **Step 2: Run tests**

```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/pytest -x -q
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
cd /home/zozo/University/dashboard
git add backend/app/main.py
git commit -m "feat: register sync router in FastAPI app"
```

---

## Task 5: Frontend types and api.ts additions

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add new types to `frontend/src/lib/types.ts`**

Append to the end of the file:

```typescript
export type SyncCourse = { id: string; name: string; code: string | null }

export type FileLeaf = {
  name: string
  type: 'file'
  size: number
  rel_path: string
}

export type DirNode = {
  name: string
  type: 'dir'
  children: TreeNode[]
}

export type TreeNode = FileLeaf | DirNode
```

- [ ] **Step 2: Add SSE stream helper and new api methods to `frontend/src/lib/api.ts`**

Add the following above the `export const api = {` line:

```typescript
async function* _readSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const parts = buf.split('\n')
    buf = parts.pop() ?? ''
    for (const part of parts) {
      if (part.startsWith('data: ')) yield part.slice(6)
    }
  }
  const tail = buf + decoder.decode()
  for (const part of tail.split('\n')) {
    if (part.startsWith('data: ')) yield part.slice(6)
  }
}
```

Then add these three methods inside the `api` object (after the `grades` entry):

```typescript
  syncCourses: () => fetch('/api/sync/courses').then(j<SyncCourse[]>),

  syncRun: async (modules: string[], mode: string, onLine: (line: string) => void): Promise<void> => {
    const r = await fetch('/api/sync/run', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ modules, mode }),
    })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    for await (const line of _readSSE(r.body!)) {
      onLine(line)
    }
  },

  fileTree: () => fetch('/api/files/tree').then(j<TreeNode[]>),
```

- [ ] **Step 3: Run existing frontend tests**

```bash
cd /home/zozo/University/dashboard/frontend && npm test -- --run
```

Expected: all pass (no tests cover new api methods yet; type changes are additive).

- [ ] **Step 4: Commit**

```bash
cd /home/zozo/University/dashboard
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat: add SyncCourse/TreeNode types and sync/fileTree api methods"
```

---

## Task 6: FileTree component and Files page

**Files:**
- Create: `frontend/src/components/FileTree.tsx`
- Create: `frontend/src/components/FileTree.module.css`
- Create: `frontend/src/routes/Files.tsx`
- Create: `frontend/src/routes/Files.module.css`

- [ ] **Step 1: Create `frontend/src/components/FileTree.module.css`**

```css
.node { font-family: var(--font-mono); font-size: 0.82rem; }

.dir {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.3rem 0.75rem; cursor: pointer; color: var(--text-2);
  user-select: none;
}
.dir:hover { color: var(--amber); }

.chevron { width: 0.7rem; display: inline-block; color: var(--muted); }

.dirName { font-weight: 600; letter-spacing: 0.04em; }

.count {
  font-size: 0.7rem; color: var(--muted);
  background: var(--bg-2); border-radius: 3px;
  padding: 0 0.35rem; margin-left: auto;
}

.file {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.2rem 0.75rem;
}

.fileBtn {
  background: none; border: none; padding: 0; cursor: pointer;
  color: var(--text); font-family: var(--font-mono); font-size: 0.82rem;
  text-align: left;
}
.fileBtn:hover { color: var(--teal); }

.size { font-size: 0.7rem; color: var(--muted); margin-left: auto; white-space: nowrap; }

.empty { color: var(--muted); font-size: 0.78rem; padding: 0.2rem 0.75rem; font-style: italic; }
```

- [ ] **Step 2: Create `frontend/src/components/FileTree.tsx`**

```tsx
import { useState } from 'react'
import { api } from '../lib/api'
import type { TreeNode } from '../lib/types'
import s from './FileTree.module.css'

function fmt(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function Node({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(depth === 0)
  const indent = { paddingLeft: `${depth * 1.25 + 0.75}rem` }

  if (node.type === 'file') {
    return (
      <div className={s.file} style={indent}>
        <button className={s.fileBtn} onClick={() => api.open(node.rel_path)}>{node.name}</button>
        <span className={s.size}>{fmt(node.size)}</span>
      </div>
    )
  }

  return (
    <div className={s.node}>
      <div className={s.dir} style={indent} onClick={() => setOpen(o => !o)}>
        <span className={s.chevron}>{open ? '▼' : '▶'}</span>
        <span className={s.dirName}>{node.name}</span>
        <span className={s.count}>{node.children.length}</span>
      </div>
      {open && (
        node.children.length === 0
          ? <div className={s.empty} style={{ paddingLeft: `${(depth + 1) * 1.25 + 0.75}rem` }}>empty</div>
          : node.children.map((child, i) => <Node key={i} node={child} depth={depth + 1} />)
      )}
    </div>
  )
}

export default function FileTree({ nodes }: { nodes: TreeNode[] }) {
  return (
    <div>
      {nodes.map((n, i) => <Node key={i} node={n} depth={0} />)}
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/routes/Files.module.css`**

```css
.h1 {
  font-family: var(--font-display); letter-spacing: 0.3em;
  font-size: 1.6rem; color: var(--amber); margin-bottom: 1.5rem;
}
.loading { color: var(--muted); font-family: var(--font-mono); font-size: 0.9rem; }
.err     { color: var(--alert); font-family: var(--font-mono); font-size: 0.9rem; }
.tree    { background: var(--bg-1); border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem 0; }
```

- [ ] **Step 4: Create `frontend/src/routes/Files.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { TreeNode } from '../lib/types'
import FileTree from '../components/FileTree'
import s from './Files.module.css'

export default function Files() {
  const [tree, setTree] = useState<TreeNode[] | null>(null)
  const [err, setErr]   = useState<string | null>(null)

  useEffect(() => {
    api.fileTree().then(setTree).catch(e => setErr(String(e)))
  }, [])

  return (
    <>
      <h1 className={s.h1}>FILES</h1>
      {!tree && !err && <div className={s.loading}>Scanning…</div>}
      {err && <div className={s.err}>{err}</div>}
      {tree && <div className={s.tree}><FileTree nodes={tree} /></div>}
    </>
  )
}
```

- [ ] **Step 5: Run frontend tests**

```bash
cd /home/zozo/University/dashboard/frontend && npm test -- --run
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd /home/zozo/University/dashboard
git add frontend/src/components/FileTree.tsx frontend/src/components/FileTree.module.css \
        frontend/src/routes/Files.tsx frontend/src/routes/Files.module.css
git commit -m "feat: FileTree component and Files page"
```

---

## Task 7: Sync page

**Files:**
- Create: `frontend/src/routes/Sync.module.css`
- Create: `frontend/src/routes/Sync.tsx`

- [ ] **Step 1: Create `frontend/src/routes/Sync.module.css`**

```css
.h1 {
  font-family: var(--font-display); letter-spacing: 0.3em;
  font-size: 1.6rem; color: var(--amber); margin-bottom: 1.5rem;
}

.section { margin-bottom: 1.5rem; }

.label {
  font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.15em;
  color: var(--muted); text-transform: uppercase; margin-bottom: 0.6rem;
}

.loading { color: var(--muted); font-family: var(--font-mono); font-size: 0.85rem; }
.err     { color: var(--alert); font-family: var(--font-mono); font-size: 0.85rem; }

.toggleRow {
  display: flex; gap: 0.5rem; margin-bottom: 0.5rem;
}
.toggleBtn {
  background: none; border: 1px solid var(--border); border-radius: 4px;
  color: var(--text-2); font-family: var(--font-mono); font-size: 0.75rem;
  padding: 0.2rem 0.6rem; cursor: pointer;
}
.toggleBtn:hover { border-color: var(--amber); color: var(--amber); }

.moduleGrid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 0.4rem;
}

.moduleRow {
  display: flex; align-items: center; gap: 0.6rem;
  background: var(--bg-1); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.4rem 0.75rem; cursor: pointer;
}
.moduleRow:hover { border-color: var(--border-hot); }
.moduleRow input { cursor: pointer; accent-color: var(--amber); }
.code  { font-family: var(--font-mono); font-size: 0.8rem; color: var(--amber); min-width: 3.5rem; }
.mname { font-size: 0.82rem; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.modeRow { display: flex; gap: 1.5rem; }
.modeOpt { display: flex; align-items: center; gap: 0.4rem; cursor: pointer; }
.modeOpt input { accent-color: var(--amber); cursor: pointer; }
.modeOpt span  { font-family: var(--font-mono); font-size: 0.82rem; color: var(--text-2); }

.runBtn {
  background: var(--amber); color: var(--bg-0); border: none; border-radius: 4px;
  font-family: var(--font-display); font-size: 1rem; letter-spacing: 0.1em;
  padding: 0.5rem 2rem; cursor: pointer; font-weight: 700;
}
.runBtn:disabled { opacity: 0.4; cursor: not-allowed; }
.runBtn:not(:disabled):hover { filter: brightness(1.15); }

.terminal {
  background: var(--bg-0); border: 1px solid var(--border); border-radius: 6px;
  font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-2);
  padding: 0.75rem 1rem; height: 320px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-all;
  margin-top: 1rem;
}
.done   { color: var(--teal); }
.failed { color: var(--alert); }
```

- [ ] **Step 2: Create `frontend/src/routes/Sync.tsx`**

```tsx
import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import type { SyncCourse } from '../lib/types'
import s from './Sync.module.css'

type Mode = 'all' | 'files' | 'grades'

export default function Sync() {
  const [courses, setCourses]   = useState<SyncCourse[] | null>(null)
  const [fetchErr, setFetchErr] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [mode, setMode]         = useState<Mode>('all')
  const [running, setRunning]   = useState(false)
  const [lines, setLines]       = useState<{ text: string; cls?: string }[]>([])
  const termRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.syncCourses()
      .then(cs => {
        setCourses(cs)
        setSelected(new Set(cs.filter(c => c.code).map(c => c.code!)))
      })
      .catch(e => setFetchErr(String(e)))
  }, [])

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [lines])

  function toggleAll() {
    if (!courses) return
    const codes = courses.filter(c => c.code).map(c => c.code!)
    if (selected.size === codes.length) setSelected(new Set())
    else setSelected(new Set(codes))
  }

  function toggleOne(code: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(code) ? next.delete(code) : next.add(code)
      return next
    })
  }

  async function handleSync() {
    if (!courses) return
    setRunning(true)
    setLines([])
    const mods = courses.filter(c => c.code && selected.has(c.code!)).map(c => c.code!)
    try {
      await api.syncRun(mods, mode, line => {
        if (line.startsWith('__exit__:')) {
          const code = parseInt(line.split(':')[1], 10)
          setLines(l => [...l, code === 0
            ? { text: 'Done.', cls: s.done }
            : { text: `Sync failed (exit ${code}).`, cls: s.failed },
          ])
        } else {
          setLines(l => [...l, { text: line }])
        }
      })
    } catch (e) {
      setLines(l => [...l, { text: `Error: ${e}`, cls: s.failed }])
    } finally {
      setRunning(false)
    }
  }

  const allCodes = courses?.filter(c => c.code).map(c => c.code!) ?? []
  const noneSelected = selected.size === 0 && mode !== 'grades'
  const canRun = !running && !!courses && !noneSelected

  return (
    <>
      <h1 className={s.h1}>SYNC</h1>

      <div className={s.section}>
        <div className={s.label}>Modules</div>
        {!courses && !fetchErr && <div className={s.loading}>Fetching from Blackboard…</div>}
        {fetchErr && <div className={s.err}>Could not load modules: {fetchErr}</div>}
        {courses && (
          <>
            <div className={s.toggleRow}>
              <button className={s.toggleBtn} onClick={toggleAll}>
                {selected.size === allCodes.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>
            <div className={s.moduleGrid}>
              {courses.map(c => (
                <label key={c.id} className={s.moduleRow}>
                  <input
                    type="checkbox"
                    checked={!!c.code && selected.has(c.code)}
                    disabled={!c.code}
                    onChange={() => c.code && toggleOne(c.code)}
                  />
                  <span className={s.code}>{c.code ?? '—'}</span>
                  <span className={s.mname}>{c.name}</span>
                </label>
              ))}
            </div>
          </>
        )}
      </div>

      <div className={s.section}>
        <div className={s.label}>What to sync</div>
        <div className={s.modeRow}>
          {(['all', 'files', 'grades'] as Mode[]).map(m => (
            <label key={m} className={s.modeOpt}>
              <input type="radio" name="mode" value={m} checked={mode === m} onChange={() => setMode(m)} />
              <span>{m === 'all' ? 'Files + Grades' : m === 'files' ? 'Files only' : 'Grades only'}</span>
            </label>
          ))}
        </div>
      </div>

      <button className={s.runBtn} disabled={!canRun} onClick={handleSync}>
        {running ? 'Syncing…' : 'Sync'}
      </button>

      {lines.length > 0 && (
        <div className={s.terminal} ref={termRef}>
          {lines.map((l, i) => (
            <div key={i} className={l.cls}>{l.text}</div>
          ))}
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 3: Run frontend tests**

```bash
cd /home/zozo/University/dashboard/frontend && npm test -- --run
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
cd /home/zozo/University/dashboard
git add frontend/src/routes/Sync.tsx frontend/src/routes/Sync.module.css
git commit -m "feat: Sync page with live module selection and streaming terminal"
```

---

## Task 8: Wire up nav and router, build frontend

**Files:**
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update `frontend/src/components/Layout.tsx`**

Replace the entire file:

```tsx
import type { ReactNode } from 'react'
import s from './Layout.module.css'

const NAV = [
  ['#/',          'HOME'],
  ['#/planner',   'PLANNER'],
  ['#/deadlines', 'DEADLINES'],
  ['#/resources', 'RESOURCES'],
  ['#/grades',    'GRADES'],
  ['#/files',     'FILES'],
  ['#/sync',      'SYNC'],
] as const

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className={s.shell}>
      <aside className={s.side}>
        <div className={s.brand}>UNI · HUB</div>
        <nav>{NAV.map(([h, l]) => <a key={h} href={h} className={s.link}>{l}</a>)}</nav>
      </aside>
      <main className={s.main}>{children}</main>
    </div>
  )
}
```

- [ ] **Step 2: Update `frontend/src/App.tsx`**

Replace the entire file:

```tsx
import Layout from './components/Layout'
import { useHashRoute } from './lib/router'
import Home from './routes/Home'
import Module from './routes/Module'
import Planner from './routes/Planner'
import Deadlines from './routes/Deadlines'
import Resources from './routes/Resources'
import Grades from './routes/Grades'
import Files from './routes/Files'
import Sync from './routes/Sync'

export default function App() {
  const h = useHashRoute()
  let page = <Home />
  if (h.startsWith('#/module/'))   page = <Module code={h.split('/')[2]} />
  else if (h === '#/planner')      page = <Planner />
  else if (h === '#/deadlines')    page = <Deadlines />
  else if (h === '#/resources')    page = <Resources />
  else if (h === '#/grades')       page = <Grades />
  else if (h === '#/files')        page = <Files />
  else if (h === '#/sync')         page = <Sync />
  return <Layout>{page}</Layout>
}
```

- [ ] **Step 3: Run frontend tests**

```bash
cd /home/zozo/University/dashboard/frontend && npm test -- --run
```

Expected: all pass.

- [ ] **Step 4: Build frontend**

```bash
cd /home/zozo/University/dashboard/frontend && npm run build
```

Expected: build completes with no errors. Output in `frontend/dist/`.

- [ ] **Step 5: Smoke-test in browser**

Start the backend (if not running):
```bash
cd /home/zozo/University/dashboard/backend && .venv/bin/uvicorn app.main:app --port 8765
```

Open `http://localhost:8765` in Edge. Verify:
- "FILES" and "SYNC" appear in the sidebar
- `/files` loads a folder tree showing FA565, FA583, FN585 with their subfolders
- `/sync` loads, fetches modules from Blackboard (spinner → module checkboxes), and "Sync" button is active
- Clicking "Sync" streams output to the terminal panel; finishes with "Done."
- After sync, revisit `/files` — any newly downloaded files appear in the tree

- [ ] **Step 6: Commit**

```bash
cd /home/zozo/University/dashboard
git add frontend/src/components/Layout.tsx frontend/src/App.tsx frontend/dist
git commit -m "feat: add Files and Sync to nav and router; rebuild dist"
```

---

## Task 9: Create dashboard GitHub repo and push

- [ ] **Step 1: Merge feature branch into main**

```bash
cd /home/zozo/University/dashboard
git checkout main
git merge feature/grade-sync --no-ff -m "feat: grades, sync UI, file tree browser"
```

- [ ] **Step 2: Create GitHub repo and push**

```bash
gh repo create university-dashboard --public --description "University Blackboard dashboard — grades, sync, file browser" --source . --remote origin --push
```

Expected: repo created at `https://github.com/zshahzada1/<username>/university-dashboard` and `main` pushed.

If `gh` is not authenticated, run `gh auth login` first.

- [ ] **Step 3: Verify**

```bash
gh repo view --web
```

Expected: opens the new repo in the browser.
