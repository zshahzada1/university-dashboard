import json, pytest
from pathlib import Path
from app.services.grades import (
    classify, find_column, compute_module, compute_grades, derive_status
)

# ── classify ────────────────────────────────────────────────────────────────

def test_classify_first():        assert classify(70) == "First"
def test_classify_2_1():          assert classify(65) == "2:1"
def test_classify_2_2():          assert classify(55) == "2:2"
def test_classify_third():        assert classify(45) == "Third"
def test_classify_fail():         assert classify(35) == "Fail"
def test_classify_boundary_2_1(): assert classify(60) == "2:1"

# ── find_column ─────────────────────────────────────────────────────────────

COLS = [
    {"name": "Task 1 - Group Presentation", "score": 68.0, "possible": 100.0, "status": "graded"},
    {"name": "Task 2 - Analytical Essay",   "score": None, "possible": 100.0, "status": "ungraded"},
]

def test_find_column_matches_substring():
    assert find_column("Task 1", COLS)["name"] == "Task 1 - Group Presentation"

def test_find_column_case_insensitive():
    assert find_column("task 2", COLS) is not None

def test_find_column_empty_name_returns_none():
    assert find_column("", COLS) is None

def test_find_column_no_match_returns_none():
    assert find_column("Exam", COLS) is None

def test_find_column_prefers_graded_over_primary():
    cols = [
        {"name": "Task 2 (Analytical Essay) - Submission", "score": None,  "possible": 100.0},
        {"name": "Task 2 (Analytical Essay) - Extension",  "score": 74.0, "possible": 100.0},
        {"name": "Task 2 (Analytical Essay) - LSP",        "score": None,  "possible": 100.0},
    ]
    result = find_column("Task 2 (Analytical Essay)", cols)
    assert result is not None
    assert result["score"] == 74.0

def test_find_column_returns_primary_when_all_ungraded():
    cols = [
        {"name": "Task 2 (Analytical Essay) - Submission", "score": None, "possible": 100.0},
        {"name": "Task 2 (Analytical Essay) - Extension",  "score": None, "possible": 100.0},
        {"name": "Task 2 (Analytical Essay) - LSP",        "score": None, "possible": 100.0},
    ]
    result = find_column("Task 2 (Analytical Essay)", cols)
    assert result is not None
    assert "Submission" in result["name"]

# ── compute_module ───────────────────────────────────────────────────────────

FA565_CFG = {
    "name": "Business Ethics",
    "course_id": "_130565_1",
    "credits": 20,
    "assessments": [
        {"title": "Task 1", "weight_percent": 40, "column_name": "Task 1"},
        {"title": "Task 2", "weight_percent": 60, "column_name": "Task 2"},
    ]
}

def test_grade_so_far_partial():
    result = compute_module(FA565_CFG, COLS)
    assert result["grade_so_far"] == 68.0          # reweighted: 68 * 40/40
    assert result["classification"] == "2:1"

def test_needed_for_first_partial():
    result = compute_module(FA565_CFG, COLS)
    # G=27.2, R=0.60, needed=(70-27.2)/0.60=71.33
    assert abs(result["needed_for_first"] - 71.3) < 0.1
    assert result["first_status"] == "possible"

def test_fully_graded_is_final():
    cols = [
        {"name": "Task 1", "score": 65.0, "possible": 100.0, "status": "graded"},
        {"name": "Task 2", "score": 70.0, "possible": 100.0, "status": "graded"},
    ]
    result = compute_module(FA565_CFG, cols)
    assert result["first_status"] == "final"
    assert result["needed_for_first"] is None

def test_first_impossible():
    cols = [
        {"name": "Task 1", "score": 20.0, "possible": 100.0, "status": "graded"},
        {"name": "Task 2", "score": None,  "possible": 100.0, "status": "ungraded"},
    ]
    result = compute_module(FA565_CFG, cols)
    # G=8.0, R=0.60, needed=(70-8)/0.60=103.3 > 100
    assert result["first_status"] == "impossible"
    assert result["needed_for_first"] > 100

def test_all_ungraded_returns_none_grade():
    cols = [
        {"name": "Task 1", "score": None, "possible": 100.0, "status": "ungraded"},
        {"name": "Task 2", "score": None, "possible": 100.0, "status": "ungraded"},
    ]
    result = compute_module(FA565_CFG, cols)
    assert result["grade_so_far"] is None

def test_weights_not_summing_to_100_flags_warning():
    cfg = {**FA565_CFG, "assessments": [
        {"title": "Task 1", "weight_percent": 40, "column_name": "Task 1"},
        {"title": "Task 2", "weight_percent": 40, "column_name": "Task 2"},
    ]}
    result = compute_module(cfg, COLS)
    assert result["weights_ok"] is False

def test_unmapped_assessment_excluded_from_math():
    cfg = {**FA565_CFG, "assessments": [
        {"title": "Task 1", "weight_percent": 40, "column_name": "Task 1"},
        {"title": "Unknown", "weight_percent": 60, "column_name": ""},  # empty = unmapped
    ]}
    cols = [{"name": "Task 1", "score": 68.0, "possible": 100.0, "status": "graded"}]
    result = compute_module(cfg, cols)
    unmapped = [a for a in result["assessments"] if a["status"] == "unmapped"]
    assert len(unmapped) == 1
    assert result["grade_so_far"] == 68.0

# ── compute_grades ───────────────────────────────────────────────────────────

ASSESSMENTS_TWO = {
    "FA565": FA565_CFG,
    "MA583": {
        "name": "MA583", "course_id": "_999_1", "credits": 20,
        "assessments": [{"title": "Exam", "weight_percent": 100, "column_name": "Exam"}]
    }
}
GRADES_TWO = {
    "synced_at": "2026-05-18T12:00:00Z",
    "FA565": {"columns": COLS},
    "MA583": {"error": "no gradebook access"},
}

def test_compute_grades_excludes_error_modules():
    result = compute_grades(ASSESSMENTS_TWO, GRADES_TWO)
    assert "MA583" in result["excluded_modules"]

def test_compute_grades_overall_with_one_eligible():
    result = compute_grades(ASSESSMENTS_TWO, GRADES_TWO)
    # Only FA565 eligible; overall = grade_so_far(FA565) = 68.0
    assert result["overall"]["grade"] == 68.0
    assert result["overall"]["classification"] == "2:1"

def test_compute_grades_synced_at_propagated():
    result = compute_grades(ASSESSMENTS_TWO, GRADES_TWO)
    assert result["synced_at"] == "2026-05-18T12:00:00Z"

def test_compute_grades_no_eligible_modules():
    grades = {"synced_at": "2026-05-18T12:00:00Z", "MA583": {"error": "no gradebook access"}}
    assessments = {"MA583": ASSESSMENTS_TWO["MA583"]}
    result = compute_grades(assessments, grades)
    assert result["overall"]["grade"] is None

def test_compute_grades_credit_weighted_overall():
    assessments = {
        "FA565": {**FA565_CFG, "credits": 20},
        "FN585": {
            "name": "FN585", "course_id": "_130574_1", "credits": 40,
            "assessments": [{"title": "A1", "weight_percent": 100, "column_name": "A1"}]
        }
    }
    grades = {
        "synced_at": "2026-05-18T12:00:00Z",
        "FA565": {"columns": [
            {"name": "Task 1", "score": 68.0, "possible": 100.0, "status": "graded"},
            {"name": "Task 2", "score": None,  "possible": 100.0, "status": "ungraded"},
        ]},
        "FN585": {"columns": [
            {"name": "A1", "score": 80.0, "possible": 100.0, "status": "graded"},
        ]},
    }
    result = compute_grades(assessments, grades)
    # FA565 grade_so_far=68, FN585 grade_so_far=80
    # overall = (68*20 + 80*40) / (20+40) = (1360+3200)/60 = 4560/60 = 76.0
    assert abs(result["overall"]["grade"] - 76.0) < 0.1

# ── derive_status ────────────────────────────────────────────────────────────

def test_derive_status_graded_when_score():
    assert derive_status(72.0, "Graded") == "graded"

def test_derive_status_submitted_when_needs_grading():
    assert derive_status(None, "NeedsGrading") == "submitted"

def test_derive_status_upcoming_when_not_attempted():
    assert derive_status(None, "NotAttempted") == "upcoming"

def test_derive_status_upcoming_when_no_status():
    assert derive_status(None, None) == "upcoming"

def test_derive_status_override_submitted():
    assert derive_status(None, None, override="submitted") == "submitted"

def test_derive_status_score_beats_override():
    assert derive_status(80.0, "Graded", override="submitted") == "graded"

def test_submitted_status_in_assessment_output():
    cols = [
        {"name": "Task 1 - Group Presentation", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": "NeedsGrading"},
        {"name": "Task 2 - Analytical Essay", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": "NotAttempted"},
    ]
    result = compute_module(FA565_CFG, cols)
    statuses = {a["title"]: a["status"] for a in result["assessments"]}
    assert statuses["Task 1"] == "submitted"
    assert statuses["Task 2"] == "upcoming"

def test_override_submitted_in_assessment_output():
    cols = [
        {"name": "Task 1 - Group Presentation", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": None},
        {"name": "Task 2 - Analytical Essay", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": None},
    ]
    result = compute_module(FA565_CFG, cols, overrides={40: "submitted"})
    statuses = {a["title"]: a["status"] for a in result["assessments"]}
    assert statuses["Task 1"] == "submitted"
    assert statuses["Task 2"] == "upcoming"

def test_find_column_prefers_submitted_over_upcoming():
    cols = [
        {"name": "Task 1 - Submission", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": "NeedsGrading"},
        {"name": "Task 1 - Extension", "score": None, "possible": 100.0,
         "status": "ungraded", "bb_status": "NotAttempted"},
    ]
    result = find_column("Task 1", cols)
    assert result["bb_status"] == "NeedsGrading"
