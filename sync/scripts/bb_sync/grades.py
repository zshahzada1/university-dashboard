from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from bb_client import BlackboardClient


def _find_col(column_name: str, cols: list[dict]) -> dict | None:
    """Substring-match column_name against available columns.

    Returns the first col whose score is not None (if any),
    else the first col whose bb_status == "NeedsGrading" (if any),
    else the first match.
    """
    matches = [c for c in cols if column_name.lower() in c["name"].lower()]
    if not matches:
        return None

    for m in matches:
        if m.get("score") is not None:
            return m
    for m in matches:
        if m.get("bb_status") == "NeedsGrading":
            return m
    return matches[0]


def _derive_status(score, bb_status: str | None) -> str:
    """Derive assignment status from grade data."""
    if score is not None:
        return "graded"
    if bb_status == "NeedsGrading":
        return "submitted"
    return "upcoming"


class GradeSyncer:
    def __init__(self, client: BlackboardClient, assessments_path: Path,
                 grades_path: Path, assignments_path: Path | None = None):
        self._client = client
        self._assessments_path = assessments_path
        self._grades_path = grades_path
        self._assignments_path = assignments_path

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
        if self._assignments_path is not None:
            self._promote_statuses(result)
        return result

    def _promote_statuses(self, grades: dict) -> None:
        if self._assignments_path is None or not self._assignments_path.exists():
            return

        assessments_config = json.loads(self._assessments_path.read_text())
        assignments = json.loads(self._assignments_path.read_text())
        assignments_lookup = {
            (a["module_code"], float(a["weighting_percent"])): a for a in assignments
        }
        changed = False

        for module_code, module_assessments in assessments_config.items():
            if module_code not in grades or "columns" not in grades[module_code]:
                continue
            grade_columns = grades[module_code]["columns"]

            for assessment in module_assessments.get("assessments", []):
                col_name = assessment.get("column_name")
                if not col_name:
                    continue

                col = _find_col(col_name, grade_columns)
                if not col:
                    continue

                derived_status = _derive_status(col.get("score"), col.get("bb_status"))
                key = (module_code, float(assessment["weight_percent"]))
                assignment_to_update = assignments_lookup.get(key)

                if not assignment_to_update:
                    continue

                current_status = assignment_to_update["status"]

                if derived_status == "graded" and current_status != "graded":
                    assignment_to_update["status"] = "graded"
                    changed = True
                elif derived_status == "submitted" and current_status == "upcoming":
                    assignment_to_update["status"] = "submitted"
                    changed = True

        if changed:
            updated_assignments = list(assignments_lookup.values())
            self._assignments_path.write_text(json.dumps(updated_assignments, indent=2))

