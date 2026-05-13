from __future__ import annotations
import json, os, threading
from pathlib import Path
from typing import Any

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

def _lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _locks_guard:
        lk = _locks.get(key)
        if lk is None:
            lk = threading.Lock()
            _locks[key] = lk
        return lk

class JsonStore:
    def __init__(self, path: Path, default: Any):
        self.path = Path(path)
        self.default = default

    def read(self) -> Any:
        if not self.path.exists():
            return self.default
        with _lock_for(self.path):
            return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, data: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _lock_for(self.path):
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)