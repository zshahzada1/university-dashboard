from pathlib import Path
from fastapi.testclient import TestClient

import pytest

@pytest.mark.skip_isolate
def test_health_and_seeds(tmp_path: Path, monkeypatch):
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