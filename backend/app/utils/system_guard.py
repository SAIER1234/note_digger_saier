"""System resource guards — prevent overload under memory pressure."""

from pathlib import Path


def get_available_memory_mb() -> int:
    """Read available system memory in MB from /proc/meminfo.
    Returns -1 on failure (non-Linux or permission error).
    """
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemAvailable" in line:
                    return int(line.split()[1]) // 1024  # kB → MB
    except Exception:
        pass
    return -1


def check_can_accept_upload(min_memory_mb: int = 500) -> tuple[bool, str]:
    """Check if the system has enough memory to accept a new transcription.

    Returns (can_accept, reason).
    """
    available = get_available_memory_mb()
    if available < 0:
        # Non-Linux or can't read — allow by default
        return True, "ok"

    if available < min_memory_mb:
        return False, (
            f"服务器当前内存不足（可用 {available}MB，需要 {min_memory_mb}MB），"
            f"请稍后重试"
        )

    return True, "ok"
