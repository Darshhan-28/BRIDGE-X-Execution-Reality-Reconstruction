"""BRIDGE-X FastAPI entrypoint (Phase 1).

AI proposes. Verification validates. Humans control consequential decisions.
Synthetic demonstration data — not real Oil India data (arrives Phase 2).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, check_db, engine, ensure_columns
from .routers import router
import app.models  # noqa: F401 — register tables


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    yield


app = FastAPI(title="BRIDGE-X", version=settings.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "up" if check_db() else "down",
        "llm": "configured" if settings.llm_configured else "fallback-only",
        "message": "Synthetic demonstration data — not real Oil India data.",
    }


@app.get("/")
def root():
    return {"app": "BRIDGE-X", "docs": "/docs", "health": "/api/health"}
