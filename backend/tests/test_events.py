from fastapi.testclient import TestClient
import app.main

def test_create_event():
    with TestClient(app.main.app) as client:
        r = client.post("/api/events", json={"title": "Study Group", "date": "2026-05-15", "kind": "study_session"})
        assert r.status_code == 201
        assert r.json()["id"].startswith("ev-")

def test_get_event():
    with TestClient(app.main.app) as client:
        r = client.get("/api/events")
        assert r.status_code == 200

def test_patch_event():
    with TestClient(app.main.app) as client:
        ev = client.post("/api/events", json={"title": "Study Group", "date": "2026-05-15", "kind": "study_session"}).json()
        r = client.patch(f"/api/events/{ev['id']}", json={"date": "2026-05-16"})
        assert r.status_code == 200
        assert r.json()["date"] == "2026-05-16"

def test_delete_event():
    with TestClient(app.main.app) as client:
        ev = client.post("/api/events", json={"title": "Delete me", "date": "2026-05-15", "kind": "other"}).json()
        r = client.delete(f"/api/events/{ev['id']}")
        assert r.status_code == 204
        r2 = client.get("/api/events")
        assert not any(x["id"] == ev["id"] for x in r2.json())