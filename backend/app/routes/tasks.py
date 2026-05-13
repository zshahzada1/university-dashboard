from __future__ import annotations
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.store import JsonStore
from app.settings import load_settings

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

class TaskIn(BaseModel):
    text: str
    module_code: Optional[str] = None
    topic_id: Optional[str] = None
    due_date: Optional[str] = None

class TaskPatch(BaseModel):
    text: Optional[str] = None
    module_code: Optional[str] = None
    topic_id: Optional[str] = None
    due_date: Optional[str] = None
    done: Optional[bool] = None

def _store(): return JsonStore(load_settings().tasks_path, default=[])

@router.get("")
def list_tasks(due: Optional[Literal["today", "week", "backlog"]] = None):
    data = _store().read()
    if due == "today":
        today = date.today().isoformat()
        return [t for t in data if t.get("due_date") == today]
    if due == "week":
        start = date.today(); end = start + timedelta(days=7)
        return [t for t in data if t.get("due_date") and start.isoformat() <= t["due_date"] < end.isoformat()]
    if due == "backlog":
        return [t for t in data if not t.get("due_date")]
    return data

@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(body: TaskIn):
    store = _store(); data = store.read()
    new = body.model_dump()
    new["id"] = f"t-{uuid.uuid4().hex[:10]}"
    new["done"] = False
    new["created_at"] = datetime.now(timezone.utc).isoformat()
    data.append(new); store.write(data)
    return new

@router.patch("/{tid}")
def patch_task(tid: str, body: TaskPatch):
    store = _store(); data = store.read()
    for t in data:
        if t["id"] == tid:
            for k, v in body.model_dump(exclude_unset=True).items(): t[k] = v
            store.write(data); return t
    raise HTTPException(404, "task not found")

@router.delete("/{tid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(tid: str):
    store = _store(); store.write([t for t in store.read() if t["id"] != tid])