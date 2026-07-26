"""Aria-AMT integration: state-of-the-art solo piano transcription.

Uses EleutherAI's Aria-AMT model (Apache 2.0 license).
Model weights: https://huggingface.co/AEmotionStudio/aria-amt-models
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional

from app.config import MODELS_DIR, ARIA_AMT_DEVICE

# Aria-AMT repo URL
ARIA_AMT_REPO = "https://github.com/EleutherAI/aria-amt.git"
ARIA_AMT_DIR = MODELS_DIR / "aria_amt_repo"

# HuggingFace model URL
HF_MODEL_URL = (
    "https://huggingface.co/AEmotionStudio/aria-amt-models/resolve/main/"
    "piano-medium-double-1.0.safetensors"
)
CHECKPOINT_PATH = MODELS_DIR / "aria_amt" / "piano-medium-double-1.0.safetensors"


def ensure_aria_amt_installed() -> bool:
    """Ensure amt package is importable. Returns True if ready."""
    if _is_aria_importable():
        return True

    raise RuntimeError(
        "Aria-AMT not installed. Run: pip install -e models_data/aria_amt_repo"
    )

    # Clone repo
    if not ARIA_AMT_DIR.exists():
        subprocess.run(
            ["git", "clone", ARIA_AMT_REPO, str(ARIA_AMT_DIR)],
            check=True,
            capture_output=True,
        )

    # Install in editable mode
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(ARIA_AMT_DIR)],
        check=True,
        capture_output=True,
    )

    return _is_aria_importable()


def ensure_model_downloaded() -> Path:
    """Download Aria-AMT model checkpoint if not present."""
    checkpoint_dir = CHECKPOINT_PATH.parent
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if not CHECKPOINT_PATH.exists():
        import urllib.request

        print(f"Downloading Aria-AMT model from HuggingFace...")
        urllib.request.urlretrieve(HF_MODEL_URL, str(CHECKPOINT_PATH))
        print(f"Model downloaded to {CHECKPOINT_PATH}")

    return CHECKPOINT_PATH


def _is_aria_importable() -> bool:
    """Check if amt package can be imported."""
    try:
        import importlib
        importlib.import_module("amt")
        return True
    except ImportError:
        return False


def transcribe_audio(
    audio_path: Path,
    output_dir: Path,
    model: str = "medium-double",
    compile_model: bool = False,
) -> Path:
    """
    Transcribe audio file to MIDI using Aria-AMT.

    Args:
        audio_path: Path to 16kHz mono WAV file
        output_dir: Directory to save MIDI output
        model: Model variant ('medium-double')
        compile_model: Use torch.compile for faster inference

    Returns:
        Path to generated MIDI file
    """
    checkpoint = ensure_model_downloaded()
    ensure_aria_amt_installed()

    cmd = [
        "aria-amt", "transcribe",
        model,
        str(checkpoint),
        "-load_path", str(audio_path),
        "-save_dir", str(output_dir),
        "-bs", "1",
    ]
    if compile_model and ARIA_AMT_DEVICE == "cuda":
        cmd.append("-compile")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"Aria-AMT transcription failed:\n"
            f"STDERR: {result.stderr}\n"
            f"STDOUT: {result.stdout}"
        )

    # Find the output MIDI file
    midi_files = sorted(output_dir.glob("*.mid"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not midi_files:
        # Also check .midi extension
        midi_files = sorted(output_dir.glob("*.midi"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not midi_files:
        raise RuntimeError(
            f"Transcription completed but no MIDI file found in {output_dir}. "
            f"Output was: {result.stdout}"
        )

    return midi_files[0]


def transcribe_audio_python(
    audio_path: Path,
    output_dir: Path,
    model: str = "medium-double",
) -> Path:
    """Transcribe audio to MIDI using Aria-AMT CLI."""
    ensure_aria_amt_installed()
    checkpoint = ensure_model_downloaded()

    # Use KMP_DUPLICATE_LIB_OK for Windows OpenMP compatibility
    env = os.environ.copy()
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    cmd = [
        "aria-amt", "transcribe",
        model,
        str(checkpoint),
        "-load_path", str(audio_path),
        "-save_dir", str(output_dir),
        "-bs", "1",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        raise RuntimeError(
            f"Aria-AMT transcription failed:\n"
            f"STDERR: {result.stderr}\n"
            f"STDOUT: {result.stdout}"
        )

    # Find output MIDI
    midi_files = sorted(
        output_dir.glob("*.mid*"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    if not midi_files:
        raise RuntimeError(f"No MIDI output found in {output_dir}")
    return midi_files[0]
