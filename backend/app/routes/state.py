from __future__ import annotations
from fastapi import APIRouter, status
from pydantic import BaseModel
from app.services.store import JsonStore
from app.settings import load_settings

router = APIRouter(prefix="/api/state", tags=["state"])

class DismissIn(BaseModel):
    date: str
    topic_id: str

def _store(): return JsonStore(load_settings().state_path, default={"dismissed": {}})

@router.get("")
def get_state(): return _store().read()

@router.post("/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(body: DismissIn):
    s = _store(); data = s.read()
    d = data.setdefault("dismissed", {})
    d.setdefault(body.date, [])
    if body.topic_id not in d[body.date]:
        d[body.date].append(body.topic_id)
    s.write(data)
