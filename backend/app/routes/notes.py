from __future__ import annotations
import re
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import PlainTextResponse
from app.settings import load_settings

router = APIRouter(prefix="/api/notes", tags=["notes"])

_SAFE = re.compile(r"^[a-z0-9_\-]+$", re.I)

def _path(module: str, topic_id: str):
    if not _SAFE.match(module) or not _SAFE.match(topic_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid identifier")
    s = load_settings()
    return s.notes_dir / module / f"{topic_id}.md"

@router.get("/{module}/{topic_id:path}", response_class=PlainTextResponse)
def get_note(module: str, topic_id: str):
    p = _path(module, topic_id)
    return p.read_text(encoding="utf-8") if p.exists() else ""

@router.put("/{module}/{topic_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def put_note(module: str, topic_id: str, request: Request):
    p = _path(module, topic_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    body = (await request.body()).decode("utf-8")
    tmp = p.with_suffix(".md.tmp"); tmp.write_text(body, encoding="utf-8")
    import os; os.replace(tmp, p)