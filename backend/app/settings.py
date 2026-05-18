from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    university_dir: Path
    data_dir: Path
    bbsync_python: Path
    bbsync_scripts_dir: Path

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

def load_settings() -> Settings:
    here = Path(__file__).resolve().parents[1]  # backend/
    home = Path.home()
    return Settings(
        university_dir=Path(os.environ.get("UNI_DIR", str(home / "University"))),
        data_dir=Path(os.environ.get("UNI_DATA_DIR", str(here / "data"))),
        bbsync_python=Path(os.environ.get(
            "BBSYNC_PYTHON",
            str(home / "bb_sync_repo" / "scripts" / ".venv" / "bin" / "python"),
        )),
        bbsync_scripts_dir=Path(os.environ.get(
            "BBSYNC_SCRIPTS_DIR",
            str(home / "bb_sync_repo" / "scripts"),
        )),
    )
