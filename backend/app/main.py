"""Note Digger — AI-powered automatic piano transcription web service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import API_PREFIX, OUTPUT_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown — cleanup handled by Celery result expiry


app = FastAPI(
    title="Note Digger",
    description="AI 自动钢琴扒谱 — 音频转五线谱",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5000",
        "http://localhost:5050",
        "http://127.0.0.1:5050",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
from app.api.transcription import router as transcription_router
from app.api.export import router as export_router

app.include_router(transcription_router, prefix=API_PREFIX)
app.include_router(export_router, prefix=API_PREFIX)


@app.get("/")
async def root():
    return {"service": "Note Digger", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
