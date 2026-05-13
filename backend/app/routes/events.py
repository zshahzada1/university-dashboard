from __future__ import annotations
import uuid
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.store import JsonStore
from app.settings import load_settings

router = APIRouter(prefix="/api/events", tags=["events"])

class EventIn(BaseModel):
    title: str
    date: str
    time: Optional[str] = None
    module_code: Optional[str] = None
    kind: Literal["exam", "meeting", "study_session", "other"] = "other"

class EventPatch(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    module_code: Optional[str] = None
    kind: Optional[Literal["exam", "meeting", "study_session", "other"]] = None

def _store(): return JsonStore(load_settings().events_path, default=[])

@router.get("")
def list_events():
    return _store().read()

@router.post("", status_code=status.HTTP_201_CREATED)
def create_event(body: EventIn):
    store = _store(); data = store.read()
    new = body.model_dump()
    new["id"] = f"ev-{uuid.uuid4().hex[:10]}"
    data.append(new); store.write(data)
    return new

@router.patch("/{eid}")
def patch_event(eid: str, body: EventPatch):
    store = _store(); data = store.read()
    for e in data:
        if e["id"] == eid:
            for k, v in body.model_dump(exclude_unset=True).items(): e[k] = v
            store.write(data); return e
    raise HTTPException(404, "event not found")

@router.delete("/{eid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(eid: str):
    store = _store(); store.write([e for e in store.read() if e["id"] != eid])