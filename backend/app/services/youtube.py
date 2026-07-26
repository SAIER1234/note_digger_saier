"""YouTube and B站 (Bilibili) audio download via yt-dlp."""

import re
import tempfile
from pathlib import Path

import yt_dlp


# Supported URL patterns
SUPPORTED_PATTERNS = {
    "youtube": r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/\S+",
    "bilibili": r"(?:https?://)?(?:www\.)?bilibili\.com/video/\S+",
}


def detect_source(url: str) -> str | None:
    """Detect the source platform from URL. Returns platform name or None."""
    for platform, pattern in SUPPORTED_PATTERNS.items():
        if re.match(pattern, url):
            return platform
    return None


def download_audio(url: str, output_dir: Path) -> dict:
    """
    Download best available audio from YouTube/B站.
    Returns dict with file_path, title, duration info.
    """
    output_template = str(output_dir / "%(title)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Find the downloaded WAV file
    title = info.get("title", "unknown")
    wav_files = list(output_dir.glob(f"*{title}*.wav"))
    if not wav_files:
        wav_files = sorted(output_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not wav_files:
        raise RuntimeError("下载完成但找不到音频文件")

    return {
        "file_path": str(wav_files[0]),
        "title": title,
        "duration": info.get("duration", 0),
        "platform": info.get("extractor_key", "unknown"),
    }


def is_supported_url(url: str) -> bool:
    """Check if URL is from a supported platform."""
    return detect_source(url) is not None
