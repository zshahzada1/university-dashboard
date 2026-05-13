from fastapi.testclient import TestClient
import app.main

def test_list_assignments_seeded():
    with TestClient(app.main.app) as client:
        r = client.get("/api/assignments"); assert r.status_code == 200
        assert any(a["module_code"] == "FA583" for a in r.json())

def test_create_assignment():
    body = {"module_code": "FA565", "assignment_title": "Quiz",
            "assignment_type": "Quiz", "description": "",
            "deadline_date": "2026-06-10", "deadline_time": "10:00",
            "weighting_percent": 10, "word_limit_or_size": "", "submission_method": "Turnitin"}
    with TestClient(app.main.app) as client:
        r = client.post("/api/assignments", json=body); assert r.status_code == 201
        assert r.json()["id"].startswith("fa565-")

def test_patch_status():
    with TestClient(app.main.app) as client:
        a = client.get("/api/assignments").json()[0]
        r = client.patch(f"/api/assignments/{a['id']}", json={"status": "submitted"})
        assert r.status_code == 200 and r.json()["status"] == "submitted"

def test_delete():
    with TestClient(app.main.app) as client:
        a = client.get("/api/assignments").json()[0]
        r = client.delete(f"/api/assignments/{a['id']}")
        assert r.status_code == 204
        assert not any(x["id"] == a["id"] for x in client.get("/api/assignments").json())