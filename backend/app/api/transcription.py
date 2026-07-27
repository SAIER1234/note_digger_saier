"""Transcription API routes — async with progress tracking."""

import shutil
import threading
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import MAX_UPLOAD_SIZE_MB, DEV_MODE
from app.utils.file_storage import generate_task_id, get_upload_path, get_output_dir
from app.services.youtube import is_supported_url
from app.middleware.auth import get_user_from_header

# In-memory task store (for DEV_MODE progress tracking)
_task_store: dict = {}

router = APIRouter(prefix="/transcribe", tags=["transcription"])


def _run_in_background(task_id: str, source_type: str, source_path: str | None = None, source_url: str | None = None, options: dict | None = None, user_id: int | None = None):
    """Run pipeline in background thread, updating progress in _task_store."""
    from app.tasks.transcription import _run_pipeline_with_progress

    def progress_callback(stage: str, percent: int):
        _task_store[task_id] = {"status": "processing", "stage": stage, "percent": percent}

    try:
        progress_callback("预处理", 5)
        result = _run_pipeline_with_progress(
            task_id=task_id,
            source_type=source_type,
            source_path=source_path,
            source_url=source_url,
            options=options or {},
            progress_callback=progress_callback,
        )
        _task_store[task_id] = result
        # Record transcription in user history
        if user_id:
            from app.models.user import record_transcription
            engine = (options or {}).get("model", "auto")
            filename = Path(source_path).name if source_path else "url"
            record_transcription(user_id, task_id, filename, engine)
    except Exception as e:
        import traceback
        _task_store[task_id] = {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


def _check_usage(user_id: int) -> tuple[bool, str]:
    """Check if user can transcribe. Returns (allowed, error_message)."""
    from app.models.user import can_transcribe
    allowed, reason = can_transcribe(user_id)
    if not allowed:
        return False, reason
    return True, ""


AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma", ".aiff", ".aif", ".opus"}
AUDIO_MAGIC = {
    b"RIFF": ".wav",
    b"ID3": ".mp3",
    b"\xff\xfb": ".mp3",
    b"\xff\xf3": ".mp3",
    b"fLaC": ".flac",
    b"OggS": ".ogg",
    b"FORM": ".aiff",
}


def validate_audio_file(filename: str, content: bytes) -> str | None:
    """Validate uploaded file is actually audio. Returns error message or None."""
    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in AUDIO_EXTENSIONS:
        return f"不支持的文件格式: {ext}。支持: {', '.join(sorted(AUDIO_EXTENSIONS))}"

    # Check magic bytes (first 4 bytes)
    if len(content) < 12:
        return "文件太小，不是有效的音频文件"

    magic = content[:4]
    expected_ext = None
    for sig, e in AUDIO_MAGIC.items():
        if magic.startswith(sig):
            expected_ext = e
            break

    # Don't fail on magic mismatch — some formats don't have clear magic
    # Just warn if there's a mismatch
    return None


def _parse_token(request: Request) -> int | None:
    """Extract and validate user token from request. Returns user_id or None."""
    auth = request.headers.get("Authorization", "")
    if not auth:
        # Also check query param for file upload compatibility
        return None
    payload = get_user_from_header(auth)
    if payload:
        return payload["user_id"]
    return None


@router.post("/file")
async def transcribe_file(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("auto"),
    arrange: bool = Form(False),
    style: str = Form("broken"),
    difficulty: str = Form("medium"),
    token: str = Form(""),
):
    """Upload an audio file for transcription. Optional token for user tracking."""
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"文件大小 {size_mb:.1f}MB 超过限制 {MAX_UPLOAD_SIZE_MB}MB")

    # Validate file type
    err = validate_audio_file(file.filename or "audio.wav", content)
    if err:
        raise HTTPException(status_code=400, detail=err)

    # Auth check: if token provided, validate and check usage
    user_id = None
    if token:
        from app.middleware.auth import get_user_from_header
        payload = get_user_from_header(f"Bearer {token}")
        if payload:
            from app.models.user import can_transcribe
            allowed, reason = can_transcribe(payload["user_id"])
            if not allowed:
                raise HTTPException(status_code=403, detail=reason)
            user_id = payload["user_id"]

    task_id = generate_task_id()
    upload_path = get_upload_path(task_id, file.filename or "audio.wav")
    upload_path.write_bytes(content)

    if DEV_MODE:
        _task_store[task_id] = {"status": "queued", "stage": "等待处理", "percent": 0}
        threading.Thread(
            target=_run_in_background,
            args=(task_id, "file", str(upload_path)),
            kwargs={"options": {"model": model, "arrange": arrange, "style": style, "difficulty": difficulty}, "user_id": user_id},
            daemon=True,
        ).start()
        return JSONResponse({"task_id": task_id, "status": "processing", "stage": "提交成功", "percent": 0})
    else:
        from app.tasks.transcription import transcribe_audio_task
        task = transcribe_audio_task.delay(
            task_id=task_id, source_type="file",
            source_path=str(upload_path), options={"model": model},
        )
        return JSONResponse({"task_id": task_id, "celery_task_id": task.id, "status": "queued"})


@router.post("/url")
async def transcribe_url(url: str = Form(...), model: str = Form("auto")):
    """Transcribe from a YouTube or B站 URL."""
    if not is_supported_url(url):
        raise HTTPException(status_code=400, detail="不支持的链接，目前支持 YouTube 和 B站")

    task_id = generate_task_id()

    if DEV_MODE:
        _task_store[task_id] = {"status": "queued", "stage": "等待处理", "percent": 0}
        threading.Thread(
            target=_run_in_background,
            args=(task_id, "url"),
            kwargs={"source_url": url, "options": {"model": model}},
            daemon=True,
        ).start()
        return JSONResponse({"task_id": task_id, "status": "processing", "stage": "提交成功", "percent": 0})
    else:
        from app.tasks.transcription import transcribe_audio_task
        task = transcribe_audio_task.delay(
            task_id=task_id, source_type="url", source_url=url, options={"model": model},
        )
        return JSONResponse({"task_id": task_id, "celery_task_id": task.id, "status": "queued", "source_url": url})


@router.post("/record")
async def transcribe_recording(file: UploadFile = File(...), model: str = Form("auto")):
    """Transcribe a microphone recording."""
    task_id = generate_task_id()
    upload_path = get_upload_path(task_id, "recording.wav")
    content = await file.read()
    upload_path.write_bytes(content)

    if DEV_MODE:
        _task_store[task_id] = {"status": "queued", "stage": "等待处理", "percent": 0}
        threading.Thread(
            target=_run_in_background,
            args=(task_id, "recording", str(upload_path)),
            kwargs={"options": {"model": model}},
            daemon=True,
        ).start()
        return JSONResponse({"task_id": task_id, "status": "processing", "stage": "提交成功", "percent": 0})
    else:
        from app.tasks.transcription import transcribe_audio_task
        task = transcribe_audio_task.delay(
            task_id=task_id, source_type="recording", source_path=str(upload_path), options={"model": model},
        )
        return JSONResponse({"task_id": task_id, "celery_task_id": task.id, "status": "queued"})


@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """Get transcription task status with real-time progress."""
    # Check in-memory store first (DEV_MODE)
    if task_id in _task_store:
        return _task_store[task_id]

    # Check file system for completed tasks
    output_dir = get_output_dir(task_id)
    musicxml_path = output_dir / "score.musicxml"
    midi_path = output_dir / "transcribed_clean.mid"

    if musicxml_path.exists() and midi_path.exists():
        return {
            "task_id": task_id,
            "status": "completed",
            "midi_url": f"/api/v1/export/{task_id}/midi",
            "musicxml_url": f"/api/v1/export/{task_id}/musicxml",
            "percent": 100,
        }

    error_file = output_dir / "error.txt"
    if error_file.exists():
        return {"task_id": task_id, "status": "failed", "error": error_file.read_text()}

    return {"task_id": task_id, "status": "not_found"}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """Delete a transcription task and its files."""
    from app.config import UPLOAD_DIR, OUTPUT_DIR
    _task_store.pop(task_id, None)
    for base in [UPLOAD_DIR, OUTPUT_DIR]:
        for d in base.rglob(task_id):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
    return {"status": "deleted", "task_id": task_id}
