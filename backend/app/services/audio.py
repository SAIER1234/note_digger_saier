"""Audio preprocessing: resampling, format conversion, validation."""

import tempfile
from pathlib import Path

import io
import librosa
import soundfile as sf
import numpy as np
from pydub import AudioSegment


# Target sample rate for Aria-AMT
TARGET_SR = 16000


def validate_audio(file_path: Path, max_duration_sec: int = 1800) -> dict:
    """Validate audio file and return metadata. Uses fast soundfile info when possible."""
    try:
        info = sf.info(str(file_path))
        sr = info.samplerate
        channels = info.channels
        duration = info.duration
    except Exception:
        # Fallback: load with librosa
        y, sr = librosa.load(str(file_path), sr=None, mono=False)
        duration = librosa.get_duration(y=y, sr=sr)
        channels = 1 if y.ndim == 1 else y.shape[0]

    if duration > max_duration_sec:
        raise ValueError(f"音频时长 {duration:.1f}s 超过最大限制 {max_duration_sec}s")

    return {
        "sample_rate": sr,
        "duration": round(duration, 2),
        "channels": channels,
    }


def preprocess_audio(input_path: Path, output_path: Path | None = None) -> Path:
    """
    Convert any audio format to mono 16kHz WAV for Aria-AMT.
    Returns path to processed file.
    """
    if output_path is None:
        output_path = input_path.with_suffix(".processed.wav")

    # Load audio: try soundfile first (fast), fall back to audioread (more formats)
    try:
        y, sr = librosa.load(str(input_path), sr=TARGET_SR, mono=True)
    except Exception:
        # Last resort: use pydub for format conversion
        audio = AudioSegment.from_file(str(input_path))
        if audio.channels > 1:
            audio = audio.set_channels(1)
        # Export to bytes in memory, then load with soundfile
        buf = io.BytesIO()
        audio.export(buf, format="wav")
        buf.seek(0)
        y, sr = sf.read(buf)
        y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR) if sr != TARGET_SR else y
        sr = TARGET_SR

    sf.write(str(output_path), y, TARGET_SR)
    return output_path


def convert_to_mp3_format(input_path: Path) -> Path:
    """Convert audio to a standard WAV format compatible with most libraries."""
    audio = AudioSegment.from_file(str(input_path))
    output_path = input_path.with_suffix(".standard.wav")
    audio = audio.set_channels(1).set_frame_rate(TARGET_SR)
    audio.export(str(output_path), format="wav")
    return output_path
