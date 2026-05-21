from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from bb_client import BlackboardClient


class GradeSyncer:
    def __init__(self, client: BlackboardClient, assessments_path: Path, grades_path: Path):
        self._client = client
        self._assessments_path = assessments_path
        self._grades_path = grades_path

    def sync(self, user_id: str, modules: list[str] | None = None) -> dict:
        assessments = json.loads(self._assessments_path.read_text())
        if modules is not None:
            assessments = {k: v for k, v in assessments.items() if k in modules}

        result: dict = {"synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

        for module_code, module_cfg in assessments.items():
            course_id = module_cfg["course_id"]
            columns = self._client.get_gradebook_columns(course_id)
            if columns is None:
                result[module_code] = {"error": "no gradebook access"}
                continue

            col_grades = []
            for col in columns:
                grade = self._client.get_column_grade(course_id, col["id"], user_id)
                score = grade.get("score")
                bb_status = grade.get("bb_status")
                col_grades.append({
                    "name": col["name"],
                    "score": score,
                    "possible": col.get("possible"),
                    "status": "graded" if score is not None else "ungraded",
                    "bb_status": bb_status,
                })
            result[module_code] = {"columns": col_grades}

        self._grades_path.write_text(json.dumps(result, indent=2))
        return result
