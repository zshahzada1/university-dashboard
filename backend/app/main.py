from __future__ import annotations
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.settings import load_settings
from app.services.seeding import ensure_seeded
from app.routes import modules, topics, assignments, tasks, events, notes, files, search, open_file, state

settings = load_settings()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_seeded(settings)
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])

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

@app.get("/api/health")
def health(): return {"ok": True}

_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")