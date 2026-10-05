from pathlib import Path
from fastapi.testclient import TestClient

import pytest

@pytest.mark.skip_isolate
def test_health_and_seeds(tmp_path: Path, monkeypatch, _test_host):
    uni = tmp_path / "uni"; uni.mkdir()
    monkeypatch.setenv("UNI_DIR", str(uni))
    monkeypatch.setenv("UNI_DATA_DIR", str(tmp_path / "data"))
    from importlib import reload
    import app.main, app.settings
    reload(app.settings); reload(app.main)
    with TestClient(app.main.app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200 and r.json() == {"ok": True}
        assert (tmp_path / "data" / "modules.json").exists()

def test_rejects_foreign_host_header():
    """DNS-rebinding guard: a request for another hostname is refused."""
    import app.main
    with TestClient(app.main.app) as client:
        r = client.get("/api/health", headers={"host": "evil.example.com"})
    assert r.status_code == 400


def test_rejects_cross_site_write():
    import app.main
    with TestClient(app.main.app) as client:
        r = client.post("/api/tasks", json={"text": "x"}, headers={"origin": "https://evil.example.com"})
        assert r.status_code == 403
        ok = client.post("/api/tasks", json={"text": "x"}, headers={"origin": "http://testserver"})
        assert ok.status_code == 201
        dev = client.post("/api/tasks", json={"text": "x"}, headers={"origin": "http://localhost:5173"})
        assert dev.status_code == 201
