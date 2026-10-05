from __future__ import annotations
import asyncio
import json
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.seeding import register_modules
from app.services.store import JsonStore
from app.settings import Settings, load_settings

router = APIRouter(tags=["sync"])

# bb_sync exit code meaning "no valid Blackboard session" (see sync/scripts/bb_sync/__main__.py).
EXIT_NOT_LOGGED_IN = 3

# The browser profile can only be open in one process at a time, so login,
# course listing and syncs are serialised. Only touched from the event loop,
# so a plain flag checked and set without an intervening await is race-free.
_bb_busy = False


class SyncRequest(BaseModel):
    modules: list[str] = []
    mode: Literal["all", "files", "grades"]


def _claim_lock() -> None:
    """Take the Blackboard lock or fail fast with 409."""
    global _bb_busy
    if _bb_busy:
        raise HTTPException(409, detail="Blackboard is busy (sync or login in progress)")
    _bb_busy = True


def _release_lock() -> None:
    global _bb_busy
    _bb_busy = False


async def _run_capture(s: Settings, args: list[str], timeout: float) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        str(s.bbsync_python), "-m", "bb_sync", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        cwd=str(s.bbsync_scripts_dir), env=s.bbsync_env(),
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def _error_detail(stderr: str, fallback: str) -> str:
    # stderr contains status lines + "ERROR: ..." — surface only the error, never a traceback
    errors = [ln.removeprefix("ERROR:").strip() for ln in stderr.splitlines() if ln.startswith("ERROR:")]
    if errors:
        return " ".join(errors)
    nonempty = [ln for ln in stderr.splitlines() if ln.strip()]
    return nonempty[-1] if nonempty else fallback


@router.get("/api/sync/courses")
async def get_courses():
    s = load_settings()
    _claim_lock()
    try:
        rc, out, err = await _run_capture(s, ["--list-courses"], timeout=120)
    except asyncio.TimeoutError:
        raise HTTPException(504, detail="Timed out talking to Blackboard (120s)")
    finally:
        _release_lock()
    if rc == EXIT_NOT_LOGGED_IN:
        raise HTTPException(401, detail="Not connected to Blackboard")
    if rc != 0:
        raise HTTPException(500, detail=_error_detail(err, "bb_sync --list-courses failed"))
    try:
        courses = json.loads(out)
    except json.JSONDecodeError as e:
        raise HTTPException(500, detail=f"Invalid JSON from bb_sync: {e}")
    JsonStore(s.bb_courses_path, default=[]).write(courses)  # names for module registration
    return courses


@router.post("/api/bb/login")
async def login():
    """Open a visible browser window and wait (up to 10 min) for the user to log in."""
    s = load_settings()
    _claim_lock()
    try:
        rc, out, err = await _run_capture(s, ["--login"], timeout=660)
    except asyncio.TimeoutError:
        raise HTTPException(504, detail="Login timed out")
    finally:
        _release_lock()
    if rc == EXIT_NOT_LOGGED_IN:
        raise HTTPException(401, detail="Login was not completed")
    if rc != 0:
        raise HTTPException(500, detail=_error_detail(err, "Could not open the login window"))
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"user": None}


def _sync_args(body: SyncRequest) -> list[str]:
    if body.mode == "grades":
        return ["--grades"] + (["--modules", *body.modules] if body.modules else [])
    args = ["--modules", *body.modules]
    if body.mode == "files":
        args.append("--no-grades")
    return args


def _register_synced(s: Settings, codes: list[str]) -> None:
    names = {c.get("code"): c.get("name") for c in JsonStore(s.bb_courses_path, default=[]).read()}
    register_modules(s, [{"code": c, "name": names.get(c) or c} for c in codes])


async def _run_sync(s: Settings, args: list[str], queue: asyncio.Queue) -> None:
    """Runs one sync, feeding output lines to queue. Owns (and always releases) the lock."""
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            str(s.bbsync_python), "-m", "bb_sync", *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            cwd=str(s.bbsync_scripts_dir), env=s.bbsync_env(),
        )
        synced: list[str] = []
        async for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").rstrip()
            if line.startswith("__synced__:"):
                synced = [c for c in line.split(":", 1)[1].split(",") if c]
                continue
            await queue.put(line)
        rc = await proc.wait()
        if synced:
            try:
                _register_synced(s, synced)
            except Exception as e:
                await queue.put(f"[warn] could not update module list: {e}")
        await queue.put(f"__exit__:{rc}")
    except Exception as e:
        await queue.put(f"ERROR: {e}")
        await queue.put("__exit__:1")
    finally:
        if proc is not None and proc.returncode is None:
            proc.kill()  # client went away mid-sync
            await proc.wait()
        _release_lock()
        queue.put_nowait(None)


@router.post("/api/sync/run")
async def run_sync(body: SyncRequest):
    if body.mode != "grades" and not body.modules:
        raise HTTPException(400, detail="No modules selected")
    s = load_settings()
    _claim_lock()
    queue: asyncio.Queue = asyncio.Queue()
    # The sync runs as its own task so the lock is released even if the response
    # stream is never consumed; closing the stream cancels (and kills) the sync.
    task = asyncio.create_task(_run_sync(s, _sync_args(body), queue))

    async def generate():
        try:
            while (line := await queue.get()) is not None:
                yield f"data: {line}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(generate(), media_type="text/event-stream")
