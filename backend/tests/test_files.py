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