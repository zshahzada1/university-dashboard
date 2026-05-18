from __future__ import annotations
import json
import subprocess
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main
import app.routes.sync as sync_module


def _make_completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def test_courses_success():
    courses = [{"id": "_1_1", "name": "FA565 Business Ethics", "code": "FA565"}]
    with patch("app.routes.sync.subprocess.run", return_value=_make_completed(json.dumps(courses))):
        with TestClient(app.main.app) as client:
            r = client.get("/api/sync/courses")
    assert r.status_code == 200
    assert r.json()[0]["code"] == "FA565"


def test_courses_subprocess_failure():
    err = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="CDP failed")
    with patch("app.routes.sync.subprocess.run", return_value=err):
        with TestClient(app.main.app) as client:
            r = client.get("/api/sync/courses")
    assert r.status_code == 500
    assert "CDP failed" in r.json()["detail"]


def test_sync_run_conflict():
    sync_module._sync_running = True
    try:
        with TestClient(app.main.app) as client:
            r = client.post("/api/sync/run", json={"modules": ["FA565"], "mode": "all"})
        assert r.status_code == 409
    finally:
        sync_module._sync_running = False
