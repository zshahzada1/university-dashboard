# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastapi>=0.110",
#   "uvicorn[standard]>=0.27",
#   "pydantic>=2.6",
#   "requests>=2.31",
#   "playwright>=1.45",
# ]
# ///
from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.resolve()

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # cp1252 can't print the banner when redirected
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(ROOT / "backend"))

# bb_sync runs as a subprocess of the backend; reuse this managed environment for it.
os.environ.setdefault("BBSYNC_PYTHON", sys.executable)
os.environ.setdefault("BBSYNC_SCRIPTS_DIR", str(ROOT / "sync" / "scripts"))

os.chdir(ROOT / "backend")
import uvicorn  # noqa: E402 — intentionally after path setup

print("\nStarting server → http://localhost:8765")
print("Open the Sync page and click 'Connect Blackboard' to log in (first time only).\n")
uvicorn.run("app.main:app", host="127.0.0.1", port=8765)
