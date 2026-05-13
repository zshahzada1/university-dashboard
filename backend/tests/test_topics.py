from fastapi.testclient import TestClient
import app.main

def test_list_topics_filter_by_module():
    with TestClient(app.main.app) as client:
        r = client.get("/api/topics", params={"module": "FA583"})
        assert r.status_code == 200
        data = r.json()
        assert "FA583" in data and len(data["FA583"]) >= 1

def test_patch_topic_confidence():
    with TestClient(app.main.app) as client:
        r = client.get("/api/topics").json()
        tid = r["FA583"][0]["id"]
        r2 = client.patch(f"/api/topics/{tid}", json={"confidence": 4})
        assert r2.status_code == 200
        assert r2.json()["confidence"] == 4
        assert r2.json()["updated_at"] is not None

def test_patch_invalid_confidence_rejected():
    with TestClient(app.main.app) as client:
        r = client.get("/api/topics").json()
        tid = r["FA583"][0]["id"]
        r2 = client.patch(f"/api/topics/{tid}", json={"confidence": 9})
        assert r2.status_code == 422

def test_post_seed_adds_new_folders():
    import os
    uni = os.environ["UNI_DIR"]
    from pathlib import Path
    (Path(uni) / "FA583" / "Week 2 - Inventory").mkdir(parents=True, exist_ok=True)
    with TestClient(app.main.app) as client:
        r = client.post("/api/topics/seed")
        assert r.status_code == 200
        titles = [t["title"] for t in r.json()["FA583"]]
        assert "Inventory" in titles