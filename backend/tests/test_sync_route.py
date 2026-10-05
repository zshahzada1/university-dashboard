from __future__ import annotations
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main
import app.routes.sync as sync_module
from app.routes.sync import SyncRequest, _sync_args


def _fake_capture(rc: int, out: str = "", err: str = ""):
    async def run(*_a, **_k):
        return rc, out, err
    return run


def test_courses_success_caches_names():
    courses = [{"id": "_1_1", "name": "FA565 Business Ethics", "code": "FA565"}]
    with patch.object(sync_module, "_run_capture", _fake_capture(0, json.dumps(courses))):
        with TestClient(app.main.app) as client:
            r = client.get("/api/sync/courses")
    assert r.status_code == 200
    assert r.json()[0]["code"] == "FA565"
    s = sync_module.load_settings()
    assert json.loads(s.bb_courses_path.read_text())[0]["code"] == "FA565"
    assert sync_module._bb_busy is False


def test_courses_not_logged_in_is_401():
    with patch.object(sync_module, "_run_capture", _fake_capture(3, err="ERROR: Not connected")):
        with TestClient(app.main.app) as client:
            r = client.get("/api/sync/courses")
    assert r.status_code == 401


def test_courses_subprocess_failure():
    with patch.object(sync_module, "_run_capture", _fake_capture(1, err="ERROR: browser failed")):
        with TestClient(app.main.app) as client:
            r = client.get("/api/sync/courses")
    assert r.status_code == 500
    assert "browser failed" in r.json()["detail"]
    assert sync_module._bb_busy is False


def test_login_returns_user():
    with patch.object(sync_module, "_run_capture", _fake_capture(0, '{"user": "s123"}\n')):
        with TestClient(app.main.app) as client:
            r = client.post("/api/bb/login")
    assert r.status_code == 200 and r.json() == {"user": "s123"}


def test_busy_returns_409():
    sync_module._bb_busy = True
    try:
        with TestClient(app.main.app) as client:
            assert client.post("/api/sync/run", json={"modules": ["FA565"], "mode": "all"}).status_code == 409
            assert client.get("/api/sync/courses").status_code == 409
            assert client.post("/api/bb/login").status_code == 409
    finally:
        sync_module._bb_busy = False


def test_invalid_mode_rejected():
    with TestClient(app.main.app) as client:
        r = client.post("/api/sync/run", json={"modules": ["FA565"], "mode": "everything"})
    assert r.status_code == 422


def test_sync_args_per_mode():
    assert _sync_args(SyncRequest(modules=["A1"], mode="all")) == ["--modules", "A1"]
    assert _sync_args(SyncRequest(modules=["A1"], mode="files")) == ["--modules", "A1", "--no-grades"]
    assert _sync_args(SyncRequest(modules=["A1"], mode="grades")) == ["--grades", "--modules", "A1"]
    assert _sync_args(SyncRequest(modules=[], mode="grades")) == ["--grades"]


def test_run_streams_and_registers_modules(tmp_path, monkeypatch):
    """End-to-end through a fake bb_sync script: lines stream, lock frees, modules register."""
    import sys
    pkg = tmp_path / "scripts" / "bb_sync"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "__main__.py").write_text("print('Syncing BY138')\nprint('__synced__:BY138')\n")
    monkeypatch.setenv("BBSYNC_PYTHON", sys.executable)
    monkeypatch.setenv("BBSYNC_SCRIPTS_DIR", str(tmp_path / "scripts"))
    s = sync_module.load_settings()
    s.bb_courses_path.parent.mkdir(parents=True, exist_ok=True)
    s.bb_courses_path.write_text(json.dumps([{"code": "BY138", "name": "BY138 - Economics"}]))

    with TestClient(app.main.app) as client:
        body = client.post("/api/sync/run", json={"modules": ["BY138"], "mode": "files"}).text

    assert "data: Syncing BY138" in body
    assert "__synced__" not in body
    assert "data: __exit__:0" in body
    mods = json.loads(s.modules_path.read_text())
    assert any(m["code"] == "BY138" and m["name"] == "BY138 - Economics" for m in mods)
    assert sync_module._bb_busy is False
