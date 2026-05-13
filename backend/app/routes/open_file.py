from __future__ import annotations
import subprocess
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.settings import load_settings

router = APIRouter(prefix="/api/open", tags=["open"])

class OpenIn(BaseModel):
    rel_path: str

@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def open_path(body: OpenIn):
    s = load_settings()
    target = (s.university_dir / body.rel_path).resolve()
    try:
        target.relative_to(s.university_dir.resolve())
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "path outside university directory")
    if not target.exists():
        raise HTTPException(404, "not found")
    subprocess.Popen(["xdg-open", str(target)], start_new_session=True)