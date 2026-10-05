from __future__ import annotations
import os
import platform
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.settings import load_settings

router = APIRouter(prefix="/api/open", tags=["open"])

class OpenIn(BaseModel):
    rel_path: str

def _is_wsl() -> bool:
    return sys.platform.startswith("linux") and "microsoft" in platform.uname().release.lower()

def _launch(target: Path) -> None:
    """Open target with the OS default application."""
    if sys.platform == "win32":
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif _is_wsl():
        win = subprocess.run(["wslpath", "-w", str(target)], capture_output=True, text=True).stdout.strip()
        subprocess.Popen(["explorer.exe", win], start_new_session=True)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)], start_new_session=True)
    else:
        subprocess.Popen(["xdg-open", str(target)], start_new_session=True)

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
    _launch(target)
