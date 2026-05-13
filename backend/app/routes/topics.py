from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.store import JsonStore
from app.services.folder_scan import scan_module_topics
from app.settings import load_settings

router = APIRouter(prefix="/api/topics", tags=["topics"])

class TopicPatch(BaseModel):
    title: Optional[str] = None
    confidence: Optional[int] = Field(default=None, ge=1, le=5)

@router.get("")
def list_topics(module: Optional[str] = None):
    s = load_settings()
    data = JsonStore(s.topics_path, default={}).read()
    if module:
        return {module: data.get(module, [])}
    return data

@router.patch("/{topic_id}")
def patch_topic(topic_id: str, body: TopicPatch):
    s = load_settings()
    store = JsonStore(s.topics_path, default={})
    data = store.read()
    for module_code, topics in data.items():
        for t in topics:
            if t["id"] == topic_id:
                if body.confidence is not None:
                    t["confidence"] = body.confidence
                if body.title is not None:
                    t["title"] = body.title
                t["updated_at"] = datetime.now(timezone.utc).isoformat()
                store.write(data)
                return t
    raise HTTPException(404, "topic not found")

@router.post("/seed")
def reseed():
    s = load_settings()
    modules = JsonStore(s.modules_path, default=[]).read()
    store = JsonStore(s.topics_path, default={})
    data = store.read()
    for m in modules:
        existing_folders = {t["folder"] for t in data.get(m["code"], [])}
        existing_ids = {t["id"] for t in data.get(m["code"], [])}
        new_index = len(data.get(m["code"], []))
        for parsed in scan_module_topics(s.university_dir / m["folder"]):
            if parsed["folder"] in existing_folders:
                continue
            new_index += 1
            tid = f"{m['code'].lower()}-t{new_index:02d}"
            while tid in existing_ids:
                new_index += 1; tid = f"{m['code'].lower()}-t{new_index:02d}"
            data.setdefault(m["code"], []).append({
                "id": tid, "title": parsed["title"], "week": parsed["week"],
                "folder": parsed["folder"], "confidence": None, "updated_at": None,
            })
    store.write(data)
    return data