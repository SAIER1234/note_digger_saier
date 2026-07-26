"""Application configuration, loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load from backend directory (resolves cwd issues with background processes)
from pathlib import Path as _Path
_env_path = _Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)
# Also try project root
load_dotenv(_Path(__file__).resolve().parent.parent.parent / ".env")

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models_data"
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

for d in [MODELS_DIR, UPLOAD_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Redis / Celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Aria-AMT
ARIA_AMT_MODEL = os.getenv("ARIA_AMT_MODEL", "medium-double")
ARIA_AMT_CHECKPOINT = os.getenv(
    "ARIA_AMT_CHECKPOINT",
    str(MODELS_DIR / "aria_amt" / "piano-medium-double-1.0.safetensors"),
)
ARIA_AMT_DEVICE = os.getenv("ARIA_AMT_DEVICE", "cpu")  # cpu | cuda

# Audio limits
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
MAX_AUDIO_DURATION_SEC = int(os.getenv("MAX_AUDIO_DURATION_SEC", "1800"))  # 30 min

# API
API_PREFIX = "/api/v1"

# Dev mode — when True, run tasks synchronously without Celery/Redis
DEV_MODE = os.getenv("DEV_MODE", "true").lower() in ("true", "1", "yes")  # default: dev mode on
