import os
from pathlib import Path
from fastapi.testclient import TestClient
import app.main

def test_search_filename():
    uni = Path(os.environ["UNI_DIR"])
    (uni / "FN585" / "Markovitz CAPM notes.pdf").write_bytes(b"stub")
    with TestClient(app.main.app) as client:
        r = client.get("/api/search", params={"q": "capm"})
        assert r.status_code == 200
        hits = r.json()
        assert any(h["name"] == "Markovitz CAPM notes.pdf" for h in hits)
        assert all("module" in h and "rel_path" in h for h in hits)