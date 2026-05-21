# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fastapi>=0.110",
#   "uvicorn[standard]>=0.27",
#   "pydantic>=2.6",
#   "websocket-client>=1.7",
#   "requests>=2.31",
# ]
# ///
from __future__ import annotations

import os
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).parent.resolve()

# ── Python path: backend app + bb_sync module ────────────────────────────────
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "sync" / "scripts" / "bb_sync"))

# ── bb_sync env: reuse this managed venv for the sync subprocess ─────────────
os.environ.setdefault("BBSYNC_PYTHON", sys.executable)
os.environ.setdefault("BBSYNC_SCRIPTS_DIR", str(ROOT / "sync" / "scripts"))


def _cdp_reachable() -> bool:
    for port in (9222, 9223):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2)
            return True
        except Exception:
            pass
    return False


if not _cdp_reachable():
    from browser_launcher import run_wizard  # type: ignore[import]
    run_wizard()

# ── start server ─────────────────────────────────────────────────────────────
os.chdir(ROOT / "backend")
import uvicorn  # noqa: E402 — intentionally after path setup

print(f"\nStarting server → http://localhost:8765\n")
uvicorn.run("app.main:app", host="127.0.0.1", port=8765)
