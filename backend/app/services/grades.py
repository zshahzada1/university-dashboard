from __future__ import annotations
import json
from pathlib import Path


def classify(grade: float) -> str:
    if grade >= 70: return "First"
    if grade >= 60: return "2:1"
    if grade >= 50: return "2:2"
    if grade >= 40: return "Third"
    return "Fail"


def find_column(column_name: str, columns: list[dict]) -> dict | None:
    if not column_name:
        return None
    needle = column_name.lower()
    for col in columns:
        if needle in col["name"].lower():
            return col
    return None


def compute_module(module_cfg: dict, raw_columns: list[dict]) -> dict:
    assessments_cfg = module_cfg["assessments"]
    weights_sum = sum(a["weight_percent"] for a in assessments_cfg)

    assessments_out = []
    graded_items: list[tuple[float, float]] = []   # (mark_pct, weight_frac)
    ungraded_weight = 0.0

    for a in assessments_cfg:
        w_frac = a["weight_percent"] / 100
        if not a["column_name"]:
            assessments_out.append({
                "title": a["title"], "weight_percent": a["weight_percent"],
                "score": None, "status": "unmapped",
            })
            continue
        col = find_column(a["column_name"], raw_columns)
        if col is None or col.get("score") is None:
            assessments_out.append({
                "title": a["title"], "weight_percent": a["weight_percent"],
                "score": None, "status": "ungraded",
            })
            ungraded_weight += w_frac
        else:
            possible = col.get("possible") or 100.0
            mark = col["score"] / possible * 100
            assessments_out.append({
                "title": a["title"], "weight_percent": a["weight_percent"],
                "score": round(mark, 1), "status": "graded",
            })
            graded_items.append((mark, w_frac))

    if not graded_items:
        return {
            "name": module_cfg["name"], "credits": module_cfg["credits"],
            "grade_so_far": None, "classification": None,
            "needed_for_first": None, "first_status": "possible",
            "weights_ok": abs(weights_sum - 100) < 0.01,
            "assessments": assessments_out,
        }

    graded_weight = sum(w for _, w in graded_items)
    grade_so_far = sum(m * w for m, w in graded_items) / graded_weight

    G = sum(m * w for m, w in graded_items)
    R = ungraded_weight

    if R == 0:
        first_status = "final"
        needed_for_first = None
    else:
        needed = (70 - G) / R
        if needed <= 0:
            first_status = "secured"
            needed_for_first = 0.0
        elif needed > 100:
            first_status = "impossible"
            needed_for_first = round(needed, 1)
        else:
            first_status = "possible"
            needed_for_first = round(needed, 1)

    return {
        "name": module_cfg["name"],
        "credits": module_cfg["credits"],
        "grade_so_far": round(grade_so_far, 1),
        "classification": classify(grade_so_far),
        "needed_for_first": needed_for_first,
        "first_status": first_status,
        "weights_ok": abs(weights_sum - 100) < 0.01,
        "assessments": assessments_out,
    }


def compute_grades(assessments_cfg: dict, grades_raw: dict) -> dict:
    synced_at = grades_raw.get("synced_at")
    modules_out: dict = {}
    excluded: list[str] = []
    eligible: list[tuple[float, int]] = []   # (grade_so_far, credits)
    total_nonerror_credits = 0

    for code, mcfg in assessments_cfg.items():
        raw = grades_raw.get(code, {})
        if "error" in raw:
            modules_out[code] = {"error": raw["error"]}
            excluded.append(code)
            continue
        total_nonerror_credits += mcfg["credits"]
        mod = compute_module(mcfg, raw.get("columns", []))
        modules_out[code] = mod
        if mod["grade_so_far"] is not None:
            eligible.append((mod["grade_so_far"], mcfg["credits"]))

    if not eligible:
        overall = {
            "grade": None, "classification": None,
            "needed_for_first": None, "first_status": "possible",
        }
    else:
        eligible_credits = sum(c for _, c in eligible)
        overall_grade = sum(g * c for g, c in eligible) / eligible_credits

        G_overall = sum(g * c for g, c in eligible) / total_nonerror_credits
        ungraded_credits = total_nonerror_credits - sum(c for _, c in eligible)
        R_overall = ungraded_credits / total_nonerror_credits if total_nonerror_credits else 0

        if R_overall == 0:
            first_status = "final"
            needed = None
        else:
            raw_needed = (70 - G_overall) / R_overall
            if raw_needed <= 0:
                first_status = "secured"
                needed = 0.0
            elif raw_needed > 100:
                first_status = "impossible"
                needed = round(raw_needed, 1)
            else:
                first_status = "possible"
                needed = round(raw_needed, 1)

        overall = {
            "grade": round(overall_grade, 1),
            "classification": classify(overall_grade),
            "needed_for_first": needed,
            "first_status": first_status,
        }

    return {
        "synced_at": synced_at,
        "overall": overall,
        "excluded_modules": excluded,
        "modules": modules_out,
    }


def load_and_compute(assessments_path: Path, grades_path: Path) -> dict:
    if not assessments_path.exists():
        return {"error": "assessments.json not found — run setup first"}
    if not grades_path.exists():
        return {"error": "grades.json not found — run: python3 -m bb_sync --grades"}
    assessments = json.loads(assessments_path.read_text())
    grades_raw = json.loads(grades_path.read_text())
    return compute_grades(assessments, grades_raw)
