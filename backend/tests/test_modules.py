from fastapi.testclient import TestClient
import app.main

def test_list_modules():
    with TestClient(app.main.app) as client:
        r = client.get("/api/modules")
        assert r.status_code == 200
        codes = {m["code"] for m in r.json()}
        assert codes == {"FA583", "FN585", "FA565"}