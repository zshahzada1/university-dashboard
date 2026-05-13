from __future__ import annotations
import re, time
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.store import JsonStore
from app.settings import load_settings

router = APIRouter(prefix="/api/assignments", tags=["assignments"])

class AssignmentIn(BaseModel):
    module_code: str
    assignment_title: str
    assignment_type: str
    description: str = ""
    deadline_date: str
    deadline_time: str = "23:59"
    weighting_percent: float = 0
    word_limit_or_size: str = ""
    submission_method: str = ""
    linked_topics: list[str] = []

class AssignmentPatch(BaseModel):
    assignment_title: Optional[str] = None
    description: Optional[str] = None
    deadline_date: Optional[str] = None
    deadline_time: Optional[str] = None
    weighting_percent: Optional[float] = None
    word_limit_or_size: Optional[str] = None
    submission_method: Optional[str] = None
    status: Optional[Literal["upcoming", "submitted", "graded"]] = None
    linked_topics: Optional[list[str]] = None

def _slug(s: str) -> str: return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

@router.get("")
def list_assignments():
    return JsonStore(load_settings().assignments_path, default=[]).read()

@router.post("", status_code=status.HTTP_201_CREATED)
def create_assignment(body: AssignmentIn):
    store = JsonStore(load_settings().assignments_path, default=[])
    data = store.read()
    new = body.model_dump()
    new["id"] = f"{body.module_code.lower()}-{_slug(body.assignment_title)}-{int(time.time())}"
    new["status"] = "upcoming"
    data.append(new); store.write(data)
    return new

@router.patch("/{aid}")
def patch_assignment(aid: str, body: AssignmentPatch):
    store = JsonStore(load_settings().assignments_path, default=[])
    data = store.read()
    for a in data:
        if a["id"] == aid:
            for k, v in body.model_dump(exclude_none=True).items(): a[k] = v
            store.write(data); return a
    raise HTTPException(404, "assignment not found")

@router.delete("/{aid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(aid: str):
    store = JsonStore(load_settings().assignments_path, default=[])
    data = [a for a in store.read() if a["id"] != aid]
    store.write(data)