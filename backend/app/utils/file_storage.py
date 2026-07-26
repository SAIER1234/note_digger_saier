"""File storage utilities for uploads and outputs."""

import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone

from app.config import UPLOAD_DIR, OUTPUT_DIR


def generate_task_id() -> str:
    return uuid.uuid4().hex[:12]


def get_upload_path(task_id: str, original_filename: str) -> Path:
    """Create dated upload directory and return file path."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    task_dir = UPLOAD_DIR / date_str / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(original_filename).suffix or ".wav"
    return task_dir / f"input{ext}"


def get_output_dir(task_id: str) -> Path:
    """Create and return output directory for a task."""
    task_dir = OUTPUT_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def cleanup_task(task_id: str) -> None:
    """Remove all files for a task."""
    for base in [UPLOAD_DIR, OUTPUT_DIR]:
        for d in base.rglob(task_id):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
