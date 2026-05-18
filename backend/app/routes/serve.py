from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.settings import load_settings

router = APIRouter(prefix="/api/serve", tags=["serve"])

@router.get("/{rel_path:path}")
def serve_file(rel_path: str):
    s = load_settings()
    target = (s.university_dir / rel_path).resolve()
    try:
        target.relative_to(s.university_dir.resolve())
    except ValueError:
        raise HTTPException(400, "path outside university directory")
    if not target.exists():
        raise HTTPException(404, "not found")
    return FileResponse(target)
