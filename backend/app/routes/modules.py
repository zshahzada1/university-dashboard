from fastapi import APIRouter
from app.services.store import JsonStore
from app.settings import load_settings

router = APIRouter(prefix="/api/modules", tags=["modules"])

@router.get("")
def list_modules():
    s = load_settings()
    return JsonStore(s.modules_path, default=[]).read()