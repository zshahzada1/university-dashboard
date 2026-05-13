from fastapi.testclient import TestClient
import app.main

def test_get_empty_note_returns_empty_string():
    with TestClient(app.main.app) as client:
        r = client.get("/api/notes/FA583/fa583-t01")
        assert r.status_code == 200 and r.text == ""

def test_put_then_get_note():
    body = "# Inventory\nFIFO vs WAC."
    with TestClient(app.main.app) as client:
        r = client.put("/api/notes/FA583/fa583-t01", content=body, headers={"Content-Type": "text/plain; charset=utf-8"})
        assert r.status_code == 204
        r2 = client.get("/api/notes/FA583/fa583-t01")
        assert r2.text == body

def test_module_traversal_rejected():
    with TestClient(app.main.app) as client:
        r = client.put("/api/notes/FA583/..%2Fevil", content="x")
        assert r.status_code == 400