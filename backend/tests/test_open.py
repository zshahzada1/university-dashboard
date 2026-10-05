from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main
import app.routes.open_file as open_file

def test_open_launches_file():
    with patch("app.routes.open_file._launch") as launch:
        with TestClient(app.main.app) as client:
            r = client.post("/api/open", json={"rel_path": "FA583/Week 1 - Tangible non-current assets"})
            assert r.status_code == 204
            assert launch.called

def test_open_rejects_path_escape():
    with TestClient(app.main.app) as client:
        r = client.post("/api/open", json={"rel_path": "../etc/passwd"})
        assert r.status_code == 400

def test_launch_uses_startfile_on_windows(tmp_path):
    with patch.object(open_file.sys, "platform", "win32"), \
         patch.object(open_file.os, "startfile", create=True) as sf:
        open_file._launch(tmp_path)
    sf.assert_called_once_with(str(tmp_path))

def test_launch_uses_explorer_on_wsl(tmp_path):
    with patch.object(open_file.sys, "platform", "linux"), \
         patch.object(open_file, "_is_wsl", return_value=True), \
         patch.object(open_file.subprocess, "run") as run, \
         patch.object(open_file.subprocess, "Popen") as popen:
        run.return_value.stdout = "C:\\x\n"
        open_file._launch(tmp_path)
    assert popen.call_args[0][0] == ["explorer.exe", "C:\\x"]

def test_launch_uses_xdg_open_on_linux(tmp_path):
    with patch.object(open_file.sys, "platform", "linux"), \
         patch.object(open_file, "_is_wsl", return_value=False), \
         patch.object(open_file.subprocess, "Popen") as popen:
        open_file._launch(tmp_path)
    assert popen.call_args[0][0] == ["xdg-open", str(tmp_path)]
