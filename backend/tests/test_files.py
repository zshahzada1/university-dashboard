import os
from pathlib import Path
from fastapi.testclient import TestClient
import app.main

def test_files_in_topic_folder():
    uni = Path(os.environ["UNI_DIR"])
    folder = uni / "FA583" / "Week 1 - Tangible non-current assets"
    (folder / "slides.pdf").write_bytes(b"%PDF-1.4 stub")
    (folder / "reading.docx").write_bytes(b"stub")

    with TestClient(app.main.app) as client:
        topics = client.get("/api/topics").json()
        tid = topics["FA583"][0]["id"]
        r = client.get("/api/files", params={"module": "FA583", "topic_id": tid})
        assert r.status_code == 200
        names = {f["name"] for f in r.json()}
        assert {"slides.pdf", "reading.docx"} <= names


def test_file_tree_returns_structure():
    uni = Path(os.environ["UNI_DIR"])
    (uni / "FA565" / "Week 1 - Intro").mkdir(parents=True, exist_ok=True)
    (uni / "FA565" / "Week 1 - Intro" / "slides.pdf").write_bytes(b"%PDF-1.4")
    (uni / "dashboard").mkdir(exist_ok=True)

    with TestClient(app.main.app) as client:
        r = client.get("/api/files/tree")
    assert r.status_code == 200
    tree = r.json()
    names = [n["name"] for n in tree]
    assert "FA565" in names
    assert "dashboard" not in names

    fa565 = next(n for n in tree if n["name"] == "FA565")
    assert fa565["type"] == "dir"
    week1 = next(n for n in fa565["children"] if n["name"] == "Week 1 - Intro")
    slide = week1["children"][0]
    assert slide["name"] == "slides.pdf"
    assert slide["type"] == "file"
    assert slide["size"] > 0
    assert slide["rel_path"] == "FA565/Week 1 - Intro/slides.pdf"


def test_file_tree_excludes_hidden_dirs():
    uni = Path(os.environ["UNI_DIR"])
    (uni / ".hidden").mkdir(exist_ok=True)
    (uni / ".hidden" / "secret.txt").write_text("x")

    with TestClient(app.main.app) as client:
        r = client.get("/api/files/tree")
    names = [n["name"] for n in r.json()]
    assert ".hidden" not in names