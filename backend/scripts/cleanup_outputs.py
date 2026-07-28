"""Clean up old transcription outputs and uploads — run via cron or manually.

Usage:
  python scripts/cleanup_outputs.py           # Remove files older than 30 days
  python scripts/cleanup_outputs.py --dry-run  # Show what would be removed
  python scripts/cleanup_outputs.py --max-age 14  # 14 days instead of 30
"""

import argparse
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BACKEND_DIR / "outputs"
UPLOADS_DIR = BACKEND_DIR / "uploads"


def cleanup(dry_run: bool = False, max_age_days: int = 30) -> dict:
    """Remove output and upload directories older than max_age_days.

    Returns dict with stats about what was cleaned.
    """
    now = time.time()
    max_age_sec = max_age_days * 86400
    stats = {"dirs_removed": 0, "files_removed": 0, "bytes_freed": 0, "dirs": []}

    for base_dir in [OUTPUTS_DIR, UPLOADS_DIR]:
        if not base_dir.exists():
            continue

        for subdir in sorted(base_dir.iterdir()):
            if not subdir.is_dir():
                continue

            # Check if directory is older than threshold
            # Use the newest file in the directory as the reference time
            newest_mtime = 0
            file_count = 0
            total_size = 0
            for f in subdir.rglob("*"):
                if f.is_file():
                    file_count += 1
                    total_size += f.stat().st_size
                    newest_mtime = max(newest_mtime, f.stat().st_mtime)

            if newest_mtime == 0:
                # Empty directory — check directory mtime
                newest_mtime = subdir.stat().st_mtime

            age_days = (now - newest_mtime) / 86400

            if newest_mtime > 0 and (now - newest_mtime) > max_age_sec:
                stats["dirs"].append({
                    "name": subdir.name,
                    "age_days": round(age_days, 1),
                    "files": file_count,
                    "size_mb": round(total_size / (1024 * 1024), 2),
                })
                stats["dirs_removed"] += 1
                stats["files_removed"] += file_count
                stats["bytes_freed"] += total_size

                if not dry_run:
                    try:
                        shutil.rmtree(subdir)
                        print(f"Removed: {subdir.name} ({age_days:.0f}d old, {total_size/1024:.0f}KB)")
                    except Exception as e:
                        print(f"Failed to remove {subdir.name}: {e}")
                        stats["dirs_removed"] -= 1
                else:
                    print(f"[DRY RUN] Would remove: {subdir.name} ({age_days:.0f}d old, {total_size/1024:.0f}KB)")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up old transcription outputs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without deleting")
    parser.add_argument("--max-age", type=int, default=30, help="Max age in days (default: 30)")
    args = parser.parse_args()

    print(f"Cleaning files older than {args.max_age} days{' [DRY RUN]' if args.dry_run else ''}...")
    stats = cleanup(dry_run=args.dry_run, max_age_days=args.max_age)

    if stats["dirs_removed"] == 0:
        print("No old files to clean up.")
    else:
        action = "Would free" if args.dry_run else "Freed"
        print(f"\n{action} {stats['bytes_freed']/1024/1024:.1f}MB "
              f"({stats['dirs_removed']} dirs, {stats['files_removed']} files)")
