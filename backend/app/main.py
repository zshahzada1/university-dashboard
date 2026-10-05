from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.settings import load_settings
from app.services.seeding import ensure_seeded
from app.routes import modules, topics, assignments, tasks, events, notes, files, search, open_file, state, grades, sync, serve

settings = load_settings()
DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_seeded(settings)
    yield

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def reject_cross_site_writes(request: Request, call_next):
    """Block state-changing requests from other websites (CSRF via 'simple' requests).

    Browsers always send Origin on cross-origin POST/PUT/PATCH/DELETE; requests
    without one (curl, scripts) come from the local machine and are allowed.
    """
    origin = request.headers.get("origin")
    if request.method not in _SAFE_METHODS and origin:
        own = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if origin != own and origin not in DEV_ORIGINS:
            return JSONResponse({"detail": "cross-origin request blocked"}, status_code=403)
    return await call_next(request)

app.add_middleware(CORSMiddleware, allow_origins=list(DEV_ORIGINS),
                   allow_methods=["*"], allow_headers=["*"])
# Outermost: rejects DNS-rebinding requests whose Host isn't this machine.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

app.include_router(modules.router)
app.include_router(topics.router)
app.include_router(assignments.router)
app.include_router(tasks.router)
app.include_router(events.router)
app.include_router(notes.router)
app.include_router(files.router)
app.include_router(search.router)
app.include_router(open_file.router)
app.include_router(state.router)
app.include_router(grades.router)
app.include_router(sync.router)
app.include_router(serve.router)

@app.get("/api/health")
def health(): return {"ok": True}

_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
