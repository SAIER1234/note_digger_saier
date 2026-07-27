"""SQLite backup utility — run via cron or manually.

Usage:
  python scripts/backup_db.py           # Backup to default location
  python scripts/backup_db.py --clean   # Keep only last 7 backups
"""

import argparse
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "note_digger.db"
BACKUP_DIR = BACKEND_DIR / "backups"


def backup() -> Path:
    """Create a timestamped backup of the SQLite database."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"note_digger_{timestamp}.db"

    # Use SQLite backup API for safe online backup
    src = sqlite3.connect(str(DB_PATH))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    src.close()
    dst.close()

    size_kb = backup_path.stat().st_size / 1024
    print(f"Backed up to {backup_path} ({size_kb:.0f} KB)")
    return backup_path


def cleanup(keep: int = 7):
    """Remove old backups, keeping the most recent N."""
    if not BACKUP_DIR.exists():
        return
    backups = sorted(BACKUP_DIR.glob("note_digger_*.db"), reverse=True)
    for old in backups[keep:]:
        old.unlink()
        print(f"Removed old backup: {old.name}")
    print(f"Kept {min(len(backups), keep)} backups")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Note Digger DB backup")
    parser.add_argument("--clean", action="store_true", help="Keep only last 7 backups")
    args = parser.parse_args()

    backup()
    if args.clean:
        cleanup()
