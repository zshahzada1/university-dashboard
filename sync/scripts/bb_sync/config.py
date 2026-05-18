import os
import re
from pathlib import Path

# Override any of these with environment variables:
#   BB_BASE_URL   — your Blackboard instance URL
#   BB_LOCAL_ROOT — where course folders are created (default: ~/University)
#   BB_COOKIE_CACHE — where extracted cookies are cached (default: ~/.cache/bb_sync/cookies.json)
BB_BASE_URL = os.environ.get("BB_BASE_URL", "https://studentcentral.brighton.ac.uk")
LOCAL_ROOT = os.environ.get("BB_LOCAL_ROOT", str(Path.home() / "University"))
COOKIE_CACHE = os.environ.get("BB_COOKIE_CACHE", str(Path.home() / ".cache" / "bb_sync" / "cookies.json"))
ASSESSMENTS_PATH = os.environ.get(
    "BB_ASSESSMENTS_PATH",
    str(Path.home() / "University" / "dashboard" / "backend" / "data" / "assessments.json")
)
GRADES_PATH = os.environ.get(
    "BB_GRADES_PATH",
    str(Path.home() / "University" / "dashboard" / "backend" / "data" / "grades.json")
)

# Maps Blackboard course name prefix → local subfolder name
# The script will auto-detect codes like FA565, FN585, FA583 from course titles.
# Add explicit overrides here if auto-detection misses one:
COURSE_OVERRIDES = {
    # "Some Long Course Name": "FA565",
}

# Regex to pull a module code from a BB course title, e.g. "FN585 - Corporate Finance"
MODULE_CODE_RE = re.compile(r'\b([A-Z]{2,4}\d{3,4})\b')

# Allowlist — only these module codes will be synced
SYNC_MODULES = {"FA565", "FN585", "FA583"}


def should_sync_course(course_name: str) -> bool:
    """Return True only if course_name contains a module code in SYNC_MODULES."""
    m = MODULE_CODE_RE.search(course_name)
    return bool(m and m.group(1) in SYNC_MODULES)


def local_path_for_course(course_name: str) -> str:
    """Return the local folder name for a given Blackboard course name."""
    if course_name in COURSE_OVERRIDES:
        return COURSE_OVERRIDES[course_name]
    m = MODULE_CODE_RE.search(course_name)
    if m:
        return m.group(1)
    # Fallback: sanitise course name as folder
    return re.sub(r'[^\w\-]', '_', course_name).strip('_')
