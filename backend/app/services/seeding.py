from __future__ import annotations
import re
from app.services.store import JsonStore
from app.services.folder_scan import scan_module_topics
from app.settings import Settings

DEFAULT_MODULES = [
    {"code": "FA583", "name": "Financial Accounting and Reporting", "color": "#ff2a6d", "folder": "FA583"},
    {"code": "FN585", "name": "Financial Modelling and Dealing",    "color": "#05d9e8", "folder": "FN585"},
    {"code": "FA565", "name": "Business Ethics and Corp Governance","color": "#b026ff", "folder": "FA565"},
]

DEFAULT_ASSIGNMENTS = [
    {"id": "fa565-essay-2", "module_code": "FA565",
     "assignment_title": "Task 2 — Analytical Essay", "assignment_type": "Essay",
     "description": "Analytical essay on a UK listed company's governance practices.",
     "deadline_date": "2026-05-15", "deadline_time": "14:00",
     "weighting_percent": 50, "word_limit_or_size": "1,500 words",
     "submission_method": "Turnitin", "status": "upcoming", "linked_topics": []},
    {"id": "fn585-coursework", "module_code": "FN585",
     "assignment_title": "Coursework Assignment", "assignment_type": "Financial Modelling",
     "description": "Implement an algorithm to exploit market inefficiency.",
     "deadline_date": "2026-05-25", "deadline_time": "23:59",
     "weighting_percent": 50, "word_limit_or_size": "Single PDF",
     "submission_method": "MyStudies", "status": "upcoming", "linked_topics": []},
    {"id": "fa583-final-exam", "module_code": "FA583",
     "assignment_title": "Final Exam", "assignment_type": "Examination",
     "description": "Final examination for FA583. Based on the June 2026 Exam Syllabus.",
     "deadline_date": "2026-06-01", "deadline_time": "09:30",
     "weighting_percent": 70, "word_limit_or_size": "3 Hours",
     "submission_method": "In-person Exam", "status": "upcoming", "linked_topics": []},
]

def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def _seed_topics(modules: list[dict], uni_dir) -> dict:
    out: dict[str, list[dict]] = {}
    for m in modules:
        mdir = uni_dir / m["folder"]
        topics = scan_module_topics(mdir)
        seeded = []
        for i, t in enumerate(topics, 1):
            tid = f"{m['code'].lower()}-t{i:02d}"
            seeded.append({"id": tid, "title": t["title"], "week": t["week"],
                           "folder": t["folder"], "confidence": None, "updated_at": None})
        out[m["code"]] = seeded
    return out

def ensure_seeded(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    modules_store = JsonStore(settings.modules_path, default=DEFAULT_MODULES)
    if not settings.modules_path.exists():
        modules_store.write(DEFAULT_MODULES)
    modules = modules_store.read()

    if not settings.topics_path.exists():
        JsonStore(settings.topics_path, default={}).write(_seed_topics(modules, settings.university_dir))

    if not settings.assignments_path.exists():
        JsonStore(settings.assignments_path, default=[]).write(DEFAULT_ASSIGNMENTS)

    for p, default in [(settings.tasks_path, []),
                       (settings.events_path, []),
                       (settings.state_path, {})]:
        if not p.exists():
            JsonStore(p, default=default).write(default)