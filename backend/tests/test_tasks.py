from datetime import date
from fastapi.testclient import TestClient
import app.main

TODAY = date.today().isoformat()

def test_create_and_list_today():
    with TestClient(app.main.app) as client:
        r = client.post("/api/tasks", json={"text": "Outline essay", "module_code": "FA565", "due_date": TODAY})
        assert r.status_code == 201; tid = r.json()["id"]
        r2 = client.get("/api/tasks", params={"due": "today"})
        ids = [t["id"] for t in r2.json()]
        assert tid in ids

def test_toggle_done():
    with TestClient(app.main.app) as client:
        t = client.post("/api/tasks", json={"text": "x", "due_date": TODAY}).json()
        r = client.patch(f"/api/tasks/{t['id']}", json={"done": True})
        assert r.json()["done"] is True

def test_delete():
    with TestClient(app.main.app) as client:
        t = client.post("/api/tasks", json={"text": "y"}).json()
        r = client.delete(f"/api/tasks/{t['id']}"); assert r.status_code == 204

def test_backlog_filter():
    with TestClient(app.main.app) as client:
        client.post("/api/tasks", json={"text": "no-date"})
        r = client.get("/api/tasks", params={"due": "backlog"})
        assert any(t["text"] == "no-date" for t in r.json())