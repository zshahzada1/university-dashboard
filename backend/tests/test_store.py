import json
from pathlib import Path
from app.services.store import JsonStore

def test_read_default(tmp_path: Path):
    store = JsonStore(tmp_path / "x.json", default=[])
    assert store.read() == []

def test_write_then_read(tmp_path: Path):
    store = JsonStore(tmp_path / "x.json", default=[])
    store.write([{"a": 1}])
    assert store.read() == [{"a": 1}]

def test_write_is_atomic(tmp_path: Path, monkeypatch):
    """If os.replace raises, the original file is untouched."""
    path = tmp_path / "x.json"
    path.write_text(json.dumps([{"orig": True}]))
    store = JsonStore(path, default=[])

    import os
    real_replace = os.replace
    def boom(*a, **k):
        raise OSError("simulated")
    monkeypatch.setattr(os, "replace", boom)

    try:
        store.write([{"new": True}])
    except OSError:
        pass

    assert json.loads(path.read_text()) == [{"orig": True}]

def test_concurrent_writes_dont_corrupt(tmp_path: Path):
    """Two threads writing dicts; final state is one of them, never partial."""
    import threading
    store = JsonStore(tmp_path / "x.json", default={})
    def w(v):
        store.write({"v": v})
    threads = [threading.Thread(target=w, args=(i,)) for i in range(20)]
    [t.start() for t in threads]; [t.join() for t in threads]
    data = store.read()
    assert "v" in data and 0 <= data["v"] < 20