from datetime import date
from fastapi.testclient import TestClient
import app.main
client = TestClient(app.main.app)

def test_dismiss_persists():
    today = date.today().isoformat()
    r = client.post("/api/state/dismiss", json={"date": today, "topic_id": "fa583-t01"})
    assert r.status_code == 204
    r2 = client.get("/api/state")
    assert "fa583-t01" in r2.json()["dismissed"].get(today, [])

def test_get_state_returns_dismissed_map():
    r = client.get("/api/state")
    assert r.status_code == 200
    assert "dismissed" in r.json()
