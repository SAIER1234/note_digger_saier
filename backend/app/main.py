"""Note Digger — AI-powered automatic piano transcription web service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
        "http://112.124.56.83",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to API endpoints."""
    from app.middleware.rate_limit import check_rate_limit, maybe_cleanup
    path = request.url.path
    if path.startswith(API_PREFIX):
        ip = request.client.host if request.client else "unknown"
        allowed, remaining = check_rate_limit(ip, path)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "请求太频繁，请稍后再试", "retry_after": 60},
            )
        maybe_cleanup()
    response = await call_next(request)
    return response

# API routes
from app.api.transcription import router as transcription_router
from app.api.export import router as export_router
from app.api.auth import router as auth_router

app.include_router(transcription_router, prefix=API_PREFIX)
app.include_router(export_router, prefix=API_PREFIX)
app.include_router(auth_router, prefix=API_PREFIX)


@app.get("/")
async def root():
    return {"service": "Note Digger", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get(f"{API_PREFIX}/health")
async def api_health_check():
    """Health check accessible via Nginx /api/ proxy."""
    return {"status": "healthy"}
