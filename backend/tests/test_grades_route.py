import json
from fastapi.testclient import TestClient
import app.main

_ASSESSMENTS = {
    "FA565": {
        "name": "Business Ethics",
        "course_id": "_130565_1",
        "credits": 20,
        "assessments": [
            {"title": "Task 2", "weight_percent": 100, "column_name": "Task 2"},
        ],
    }
}

_GRADES = {
    "synced_at": "2026-05-18T12:00:00Z",
    "FA565": {
        "columns": [
            {"name": "Task 2 - Submission", "score": None, "possible": 100.0, "status": "ungraded"}
        ]
    },
}


def test_get_grades_returns_structure(tmp_path):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / "assessments.json").write_text(json.dumps(_ASSESSMENTS))
    (d / "grades.json").write_text(json.dumps(_GRADES))
    with TestClient(app.main.app) as client:
        r = client.get("/api/grades")
    assert r.status_code == 200
    body = r.json()
    assert "modules" in body
    assert "overall" in body
    assert "synced_at" in body


def test_get_grades_missing_grades_json(tmp_path):
    d = tmp_path / "data"
    d.mkdir(exist_ok=True)
    (d / "assessments.json").write_text(json.dumps(_ASSESSMENTS))
    with TestClient(app.main.app) as client:
        r = client.get("/api/grades")
    assert r.status_code == 200
    assert "error" in r.json()


def test_get_grades_missing_both_files():
    with TestClient(app.main.app) as client:
        r = client.get("/api/grades")
    assert r.status_code == 200
    assert "error" in r.json()
