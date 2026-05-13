from __future__ import annotations
import re
from pathlib import Path
from typing import Optional, TypedDict

_SKIP = {"module information", "study skills", "assessment information",
         "assessment submission points", "coursework resources"}

# (week, title) extractor
_PATTERNS = [
    re.compile(r"^Topic\s+\d+\s*_\s*Week\s+(\d+)\s*[-–]\s*(.+)$", re.I),
    re.compile(r"^Week\s+(\d+)\s*[-–:_]\s*(.+)$", re.I),
    re.compile(r"^Topic\s+(\d+)\s*[-–:_]\s*(.+)$", re.I),
    re.compile(r"^Part\s+\d+\s*[_:-]\s*(.+)$", re.I),
]

class TopicParse(TypedDict):
    week: Optional[int]
    title: str

def parse_topic_folder(name: str) -> Optional[TopicParse]:
    base = name.strip()
    if base.lower() in _SKIP:
        return None
    for pat in _PATTERNS[:3]:
        m = pat.match(base)
        if m:
            return {"week": int(m.group(1)), "title": m.group(2).strip()}
    m = _PATTERNS[3].match(base)
    if m:
        return {"week": None, "title": m.group(1).strip()}
    return None

def scan_module_topics(module_dir: Path) -> list[dict]:
    """Return list of {folder, week, title} for each topic-looking subfolder."""
    if not module_dir.exists():
        return []
    out = []
    for child in sorted(module_dir.iterdir()):
        if not child.is_dir():
            continue
        parsed = parse_topic_folder(child.name)
        if parsed:
            out.append({"folder": child.name, **parsed})
    return out