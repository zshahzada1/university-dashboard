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
