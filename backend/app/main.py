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

# Request logging middleware (first, so it wraps all others)
from app.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

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


@app.get(f"{API_PREFIX}/system/status")
async def system_status():
    """System status: uptime, memory, disk, transcription stats."""
    import os, time, sqlite3
    from app.config import BASE_DIR

    # Uptime (from /proc/uptime on Linux)
    uptime_sec = 0
    try:
        with open("/proc/uptime") as f:
            uptime_sec = float(f.read().split()[0])
    except Exception:
        pass

    # Memory
    mem = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemTotal" in line:
                    mem["total_kb"] = int(line.split()[1])
                elif "MemAvailable" in line:
                    mem["available_kb"] = int(line.split()[1])
    except Exception:
        pass

    # Disk
    disk = {}
    try:
        stat = os.statvfs(str(BASE_DIR))
        disk["free_gb"] = round((stat.f_frsize * stat.f_bavail) / (1024**3), 1)
        disk["total_gb"] = round((stat.f_frsize * stat.f_blocks) / (1024**3), 1)
    except Exception:
        pass

    # Transcription count
    total_uploads = 0
    try:
        db = sqlite3.connect(str(BASE_DIR / "note_digger.db"))
        row = db.execute("SELECT COUNT(*) FROM transcription_history").fetchone()
        if row:
            total_uploads = row[0]
        db.close()
    except Exception:
        pass

    # Output/upload directory sizes
    data_dirs = {}
    for label, dir_path in [
        ("outputs_mb", BASE_DIR / "outputs"),
        ("uploads_mb", BASE_DIR / "uploads"),
    ]:
        try:
            if dir_path.exists():
                total = sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file())
                data_dirs[label] = round(total / (1024 * 1024), 1)
            else:
                data_dirs[label] = 0.0
        except Exception:
            data_dirs[label] = -1

    # Count old files (>30 days)
    import time as _time
    old_file_count = 0
    now = _time.time()
    thirty_days = 30 * 86400
    try:
        for d in [BASE_DIR / "outputs", BASE_DIR / "uploads"]:
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file() and (now - f.stat().st_mtime) > thirty_days:
                        old_file_count += 1
    except Exception:
        pass

    # Log stats
    from app.middleware.logging import get_log_stats
    log_stats = get_log_stats()

    return {
        "status": "healthy",
        "uptime_hours": round(uptime_sec / 3600, 1),
        "memory": mem,
        "disk": disk,
        "total_transcriptions": total_uploads,
        "data": data_dirs,
        "old_files_count": old_file_count,
        "requests_today": log_stats["requests_today"],
        "errors": {
            "5xx": log_stats["errors_5xx"],
            "4xx": log_stats["errors_4xx"],
        },
        "recent_errors": log_stats["recent_errors"],
    }
