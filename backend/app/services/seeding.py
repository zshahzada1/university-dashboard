from __future__ import annotations
import re
from pathlib import Path
from app.services.store import JsonStore
from app.services.folder_scan import scan_module_topics
from app.settings import Settings

MODULE_CODE_RE = re.compile(r"^[A-Z]{2,4}\d{3,4}$")

# Muted palette cycled for newly discovered modules.
PALETTE = ["#2F5040", "#5E2D44", "#2C4E80", "#7A5B1E", "#3E3A6E", "#1F5E5B",
           "#6B3A2A", "#4A5A23", "#5A2E6B", "#2D5566"]

def _color(i: int) -> str:
    return PALETTE[i % len(PALETTE)]

def discover_modules(uni_dir: Path) -> list[dict]:
    """One module per folder in the university dir named like a module code (e.g. BY138)."""
    if not uni_dir.exists():
        return []
    codes = sorted(p.name for p in uni_dir.iterdir() if p.is_dir() and MODULE_CODE_RE.match(p.name))
    return [{"code": c, "name": c, "color": _color(i), "folder": c} for i, c in enumerate(codes)]

def _new_topics(module: dict, existing: list[dict], uni_dir: Path) -> list[dict]:
    """Topic entries for topic folders not yet tracked, with ids that don't collide."""
    existing_folders = {t["folder"] for t in existing}
    existing_ids = {t["id"] for t in existing}
    index = len(existing)
    out = []
    for parsed in scan_module_topics(uni_dir / module["folder"]):
        if parsed["folder"] in existing_folders:
            continue
        index += 1
        tid = f"{module['code'].lower()}-t{index:02d}"
        while tid in existing_ids:
            index += 1
            tid = f"{module['code'].lower()}-t{index:02d}"
        existing_ids.add(tid)
        out.append({"id": tid, "title": parsed["title"], "week": parsed["week"],
                    "folder": parsed["folder"], "confidence": None, "updated_at": None})
    return out

def reseed_topics(settings: Settings) -> dict:
    """Add topics for any new topic folders across all modules; existing topics are kept."""
    modules = JsonStore(settings.modules_path, default=[]).read()
    store = JsonStore(settings.topics_path, default={})
    data = store.read()
    for m in modules:
        current = data.setdefault(m["code"], [])
        current.extend(_new_topics(m, current, settings.university_dir))
    store.write(data)
    return data

def register_modules(settings: Settings, courses: list[dict]) -> list[dict]:
    """Add synced Blackboard courses ({code, name}) to modules.json and pick up their topics.

    Existing entries keep their colour and any name the user set; a placeholder name
    (the bare code, from folder discovery) is replaced by the Blackboard course title.
    """
    store = JsonStore(settings.modules_path, default=[])
    modules = store.read()
    by_code = {m["code"]: m for m in modules}
    for c in courses:
        code, name = c.get("code"), (c.get("name") or "").strip()
        if not code:
            continue
        if code in by_code:
            if by_code[code]["name"] == code and name:
                by_code[code]["name"] = name
            continue
        entry = {"code": code, "name": name or code, "color": _color(len(modules)), "folder": code}
        modules.append(entry)
        by_code[code] = entry
    store.write(modules)
    reseed_topics(settings)
    return modules

def ensure_seeded(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if not settings.modules_path.exists():
        JsonStore(settings.modules_path, default=[]).write(discover_modules(settings.university_dir))

    if not settings.topics_path.exists():
        JsonStore(settings.topics_path, default={}).write({})
        reseed_topics(settings)

    for p, default in [(settings.assignments_path, []),
                       (settings.tasks_path, []),
                       (settings.events_path, []),
                       (settings.state_path, {})]:
        if not p.exists():
            JsonStore(p, default=default).write(default)
