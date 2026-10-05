from __future__ import annotations
from pathlib import Path

def filename_search(uni_dir: Path, modules: list[dict], q: str, limit: int = 50) -> list[dict]:
    q = q.lower().strip()
    if not q: return []
    out: list[dict] = []
    for m in modules:
        base = uni_dir / m["folder"]
        if not base.exists(): continue
        for p in base.rglob("*"):
            rel = p.relative_to(uni_dir).as_posix()
            if p.is_file() and not p.name.startswith(".") and q in rel.lower():
                out.append({"name": p.name, "rel_path": rel,
                            "module": m["code"]})
                if len(out) >= limit: return out
    return out