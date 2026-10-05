import os
import re
from pathlib import Path

# Repo root: bb_sync/ -> scripts/ -> sync/ -> <repo>
_REPO = Path(__file__).resolve().parents[3]
_DATA = _REPO / "backend" / "data"

# Override any of these with environment variables:
#   BB_BASE_URL    — your Blackboard instance URL
#   BB_LOCAL_ROOT  — where course folders are created (default: ~/University)
#   BB_PROFILE_DIR — dedicated browser profile holding the Blackboard login
#   BB_SYNC_MODULES — comma-separated default allowlist (default: current term's courses)
BB_BASE_URL = os.environ.get("BB_BASE_URL", "https://studentcentral.brighton.ac.uk")
LOCAL_ROOT = os.environ.get("BB_LOCAL_ROOT", str(Path.home() / "University"))
PROFILE_DIR = os.environ.get("BB_PROFILE_DIR", str(Path.home() / ".uni-dashboard" / "bb-profile"))

# Chromium-based browser executable used for the Blackboard window. Defaults to Brave
# when installed; otherwise BbSession falls back to Edge, Chrome, then bundled Chromium.
_BRAVE_PATHS = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    str(Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/Application/brave.exe"),
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/usr/bin/brave-browser",
]
BROWSER_PATH = os.environ.get("BB_BROWSER_PATH") or next(
    (p for p in _BRAVE_PATHS if Path(p).exists()), None)
ASSESSMENTS_PATH = os.environ.get("BB_ASSESSMENTS_PATH", str(_DATA / "assessments.json"))
GRADES_PATH = os.environ.get("BB_GRADES_PATH", str(_DATA / "grades.json"))
ASSIGNMENTS_PATH = os.environ.get("BB_ASSIGNMENTS_PATH", str(_DATA / "assignments.json"))

# Maps Blackboard course name prefix → local subfolder name
# The script will auto-detect codes like FA565, FN585, FA583 from course titles.
# Add explicit overrides here if auto-detection misses one:
COURSE_OVERRIDES = {
    # "Some Long Course Name": "FA565",
}

# Regex to pull a module code from a BB course title, e.g. "FN585 - Corporate Finance"
MODULE_CODE_RE = re.compile(r'\b([A-Z]{2,4}\d{3,4})\b')
_YEAR_RE = re.compile(r'\b(20\d\d)\b')

# Optional explicit allowlist. Empty means "sync the current term's courses".
SYNC_MODULES = {
    c.strip().upper() for c in os.environ.get("BB_SYNC_MODULES", "").split(",") if c.strip()
}


def module_code(course_name: str) -> str | None:
    m = MODULE_CODE_RE.search(course_name or "")
    return m.group(1) if m else None


def should_sync_course(course_name: str) -> bool:
    """Return True only if course_name contains a module code in SYNC_MODULES."""
    code = module_code(course_name)
    return bool(code and code in SYNC_MODULES)


def current_term_codes(courses: list[dict]) -> set[str]:
    """Module codes for the term with the most coded courses (mirrors the Sync page's 'This year').

    Falls back to every coded course when no course carries a term id.
    """
    by_term: dict[str, set[str]] = {}
    term_year: dict[str, int] = {}
    coded: set[str] = set()
    for c in courses:
        code = module_code(c.get("name", ""))
        if not code:
            continue
        coded.add(code)
        if c.get("term_id"):
            by_term.setdefault(c["term_id"], set()).add(code)
            year = max((int(y) for y in _YEAR_RE.findall(c.get("name", ""))), default=0)
            term_year[c["term_id"]] = max(term_year.get(c["term_id"], 0), year)
    if by_term:
        # Most courses wins; ties (several full years) go to the latest year in the titles.
        best = max(by_term, key=lambda t: (len(by_term[t]), term_year.get(t, 0)))
        return by_term[best]
    return coded


def local_path_for_course(course_name: str) -> str:
    """Return the local folder name for a given Blackboard course name."""
    if course_name in COURSE_OVERRIDES:
        return COURSE_OVERRIDES[course_name]
    code = module_code(course_name)
    if code:
        return code
    # Fallback: sanitise course name as folder
    return re.sub(r'[^\w\-]', '_', course_name).strip('_')
