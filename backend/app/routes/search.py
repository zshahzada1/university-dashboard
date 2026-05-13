from fastapi import APIRouter
from app.services.store import JsonStore
from app.services.search import filename_search
from app.settings import load_settings

router = APIRouter(prefix="/api/search", tags=["search"])

@router.get("")
def search(q: str = ""):
    s = load_settings()
    mods = JsonStore(s.modules_path, default=[]).read()
    return filename_search(s.university_dir, mods, q)