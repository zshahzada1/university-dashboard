from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.services.store import JsonStore
from app.settings import load_settings

router = APIRouter(prefix="/api/files", tags=["files"])

@router.get("")
def list_files(module: str, topic_id: str):
    s = load_settings()
    mods = JsonStore(s.modules_path, default=[]).read()
    mod = next((m for m in mods if m["code"] == module), None)
    if not mod: raise HTTPException(404, "unknown module")
    topics = JsonStore(s.topics_path, default={}).read().get(module, [])
    t = next((x for x in topics if x["id"] == topic_id), None)
    if not t: raise HTTPException(404, "unknown topic")
    folder: Path = s.university_dir / mod["folder"] / t["folder"]
    if not folder.exists(): return []
    out = []
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            rel = p.relative_to(s.university_dir)
            out.append({"name": p.name, "rel_path": str(rel), "size": p.stat().st_size})
    return out