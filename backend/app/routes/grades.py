from fastapi import APIRouter
from app.services.grades import load_and_compute
from app.settings import load_settings

router = APIRouter(prefix="/api/grades", tags=["grades"])


@router.get("")
def get_grades():
    s = load_settings()
    return load_and_compute(s.assessments_path, s.grades_path, s.assignments_path)
