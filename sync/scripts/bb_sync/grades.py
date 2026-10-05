from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from bb_client import BlackboardClient
from config import module_code

# Keep in sync with backend/app/services/grades.py::find_column
_VARIANT_KEYWORDS = frozenset(("extension", "lsp", "referral", "deferral"))


def _find_col(column_name: str, cols: list[dict]) -> dict | None:
    """Substring-match column_name against available columns.

    Prefers a graded column, then a submitted one, then the primary column
    (skipping extension/LSP/referral/deferral variants).
    """
    if not column_name:
        return None
    needle = column_name.lower()
    matches = [c for c in cols if needle in c["name"].lower()]
    if not matches:
        return None
    for m in matches:
        if m.get("score") is not None:
            return m
    for m in matches:
        if m.get("bb_status") == "NeedsGrading":
            return m
    primary = [m for m in matches if not any(kw in m["name"].lower() for kw in _VARIANT_KEYWORDS)]
    return primary[0] if primary else matches[0]


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

    def sync(self, user_id: str, modules: list[str] | None = None,
             courses: list[dict] | None = None) -> dict:
        assessments = json.loads(self._assessments_path.read_text(encoding="utf-8"))
        if modules is not None:
            assessments = {k: v for k, v in assessments.items() if k in modules}
        course_ids = {module_code(c.get("name", "")): c["id"] for c in (courses or [])}

        result: dict = {"synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

        for code, module_cfg in assessments.items():
            course_id = module_cfg.get("course_id") or course_ids.get(code)
            if not course_id:
                result[code] = {"error": "course not found on Blackboard"}
                continue
            columns = self._client.get_gradebook_columns(course_id)
            if columns is None:
                result[code] = {"error": "no gradebook access"}
                continue

            grades = self._client.get_user_grades(course_id, user_id)
            col_grades = []
            for col in columns:
                if grades is None:  # bulk endpoint unavailable — fall back to per-column
                    grade = self._client.get_column_grade(course_id, col["id"], user_id)
                else:
                    grade = grades.get(col["id"], {})
                score = grade.get("score")
                col_grades.append({
                    "name": col["name"],
                    "score": score,
                    "possible": col.get("possible"),
                    "status": "graded" if score is not None else "ungraded",
                    "bb_status": grade.get("bb_status"),
                })
            result[code] = {"columns": col_grades}

        self._grades_path.parent.mkdir(parents=True, exist_ok=True)
        self._grades_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if self._assignments_path is not None:
            self._promote_statuses(result)
        return result

    def _promote_statuses(self, grades: dict) -> None:
        if self._assignments_path is None or not self._assignments_path.exists():
            return

        assessments_config = json.loads(self._assessments_path.read_text(encoding="utf-8"))
        assignments = json.loads(self._assignments_path.read_text(encoding="utf-8"))
        changed = False

        for code, module_assessments in assessments_config.items():
            if code not in grades or "columns" not in grades[code]:
                continue
            grade_columns = grades[code]["columns"]

            for assessment in module_assessments.get("assessments", []):
                col = _find_col(assessment.get("column_name"), grade_columns)
                if not col:
                    continue
                target = _match_assignment(assignments, code, assessment)
                if target is None:
                    continue

                derived = _derive_status(col.get("score"), col.get("bb_status"))
                current = target["status"]
                if derived == "graded" and current != "graded":
                    target["status"] = "graded"
                    changed = True
                elif derived == "submitted" and current == "upcoming":
                    target["status"] = "submitted"
                    changed = True

        if changed:
            # Assignments are updated in place, so the list is written back whole.
            self._assignments_path.write_text(json.dumps(assignments, indent=2), encoding="utf-8")


def _match_assignment(assignments: list[dict], code: str, assessment: dict) -> dict | None:
    """Find the assignment for an assessment: by title, else by weighting when unambiguous."""
    in_module = [a for a in assignments if a.get("module_code") == code]
    title = (assessment.get("title") or "").strip().lower()
    by_title = [a for a in in_module if a.get("assignment_title", "").strip().lower() == title]
    if len(by_title) == 1:
        return by_title[0]
    weight = float(assessment["weight_percent"])
    by_weight = [a for a in in_module if float(a.get("weighting_percent", -1)) == weight]
    return by_weight[0] if len(by_weight) == 1 else None
