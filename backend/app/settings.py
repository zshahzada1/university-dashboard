from __future__ import annotations
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field

REPO_ROOT = Path(__file__).resolve().parents[2]  # backend/app -> backend -> <repo>

@dataclass(frozen=True)
class Settings:
    university_dir: Path
    data_dir: Path
    bbsync_python: Path
    bbsync_scripts_dir: Path
    allowed_hosts: tuple[str, ...] = field(default=("localhost", "127.0.0.1"))

    @property
    def modules_path(self): return self.data_dir / "modules.json"
    @property
    def topics_path(self):  return self.data_dir / "topics.json"
    @property
    def assignments_path(self): return self.data_dir / "assignments.json"
    @property
    def tasks_path(self): return self.data_dir / "tasks.json"
    @property
    def events_path(self): return self.data_dir / "events.json"
    @property
    def state_path(self): return self.data_dir / "state.json"
    @property
    def notes_dir(self): return self.data_dir / "notes"
    @property
    def assessments_path(self): return self.data_dir / "assessments.json"
    @property
    def grades_path(self): return self.data_dir / "grades.json"
    @property
    def bb_courses_path(self): return self.data_dir / "bb_courses.json"

    def bbsync_env(self) -> dict[str, str]:
        """Environment for the bb_sync subprocess: point it at this backend's folders."""
        return {
            **os.environ,
            "PYTHONUNBUFFERED": "1",  # stream sync log lines as they happen
            "PYTHONIOENCODING": "utf-8",
            "BB_LOCAL_ROOT": str(self.university_dir),
            "BB_ASSESSMENTS_PATH": str(self.assessments_path),
            "BB_GRADES_PATH": str(self.grades_path),
            "BB_ASSIGNMENTS_PATH": str(self.assignments_path),
        }

def load_settings() -> Settings:
    here = REPO_ROOT / "backend"
    hosts = os.environ.get("UNI_ALLOWED_HOSTS", "localhost,127.0.0.1")
    return Settings(
        university_dir=Path(os.environ.get("UNI_DIR", str(Path.home() / "University"))),
        data_dir=Path(os.environ.get("UNI_DATA_DIR", str(here / "data"))),
        bbsync_python=Path(os.environ.get("BBSYNC_PYTHON", sys.executable)),
        bbsync_scripts_dir=Path(os.environ.get("BBSYNC_SCRIPTS_DIR", str(REPO_ROOT / "sync" / "scripts"))),
        allowed_hosts=tuple(h.strip() for h in hosts.split(",") if h.strip()),
    )
