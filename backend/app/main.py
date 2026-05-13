from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.settings import load_settings
from app.services.seeding import ensure_seeded
from app.routes import modules, topics, assignments, tasks

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

@app.get("/api/health")
def health(): return {"ok": True}