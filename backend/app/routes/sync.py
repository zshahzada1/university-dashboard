from __future__ import annotations
import asyncio
import json
import subprocess
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.settings import load_settings

router = APIRouter(prefix="/api/sync", tags=["sync"])

_sync_running = False


class SyncRequest(BaseModel):
    modules: list[str]
    mode: str  # "all" | "files" | "grades"


@router.get("/courses")
def get_courses():
    s = load_settings()
    try:
        result = subprocess.run(
            [str(s.bbsync_python), "-m", "bb_sync", "--list-courses"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(s.bbsync_scripts_dir),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(500, detail="Course fetch timed out (30s). Is Edge open and logged in?")
    if result.returncode != 0:
        # stderr contains status lines + "ERROR: ..." — surface only the error
        error_lines = [
            ln.removeprefix("ERROR:").strip()
            for ln in result.stderr.splitlines()
            if ln.startswith("ERROR:")
        ]
        if not error_lines:
            # Avoid leaking a full traceback — surface only the last meaningful line
            nonempty = [ln for ln in result.stderr.splitlines() if ln.strip()]
            msg = nonempty[-1] if nonempty else "bb_sync --list-courses failed"
        else:
            msg = " ".join(error_lines)
        raise HTTPException(500, detail=msg)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise HTTPException(500, detail=f"Invalid JSON from bb_sync: {e}")


@router.post("/run")
async def run_sync(body: SyncRequest):
    global _sync_running
    if _sync_running:
        raise HTTPException(409, detail="Sync already running")
    if body.mode != "grades" and not body.modules:
        raise HTTPException(400, detail="No modules selected")

    _sync_running = True  # set before yielding the response to close the TOCTOU window
    s = load_settings()
    args = [str(s.bbsync_python), "-m", "bb_sync"]

    if body.mode == "grades":
        args.append("--grades")
    else:
        args.extend(["--modules"] + body.modules)

    async def generate():
        global _sync_running
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(s.bbsync_scripts_dir),
            )
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                yield f"data: {line.decode().rstrip()}\n\n"
            await proc.wait()
            yield f"data: __exit__:{proc.returncode}\n\n"
        finally:
            _sync_running = False

    return StreamingResponse(generate(), media_type="text/event-stream")
