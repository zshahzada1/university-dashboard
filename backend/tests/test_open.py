from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main

def test_open_runs_xdg_open():
    with patch("app.routes.open_file.subprocess.Popen") as p:
        with TestClient(app.main.app) as client:
            r = client.post("/api/open", json={"rel_path": "FA583/Week 1 - Tangible non-current assets"})
            assert r.status_code == 204
            assert p.called

def test_open_rejects_path_escape():
    with TestClient(app.main.app) as client:
        r = client.post("/api/open", json={"rel_path": "../etc/passwd"})
        assert r.status_code == 400