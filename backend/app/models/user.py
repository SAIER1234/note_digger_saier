"""User model and database for authentication and freemium tracking.

Uses SQLite — zero extra process, zero extra memory.
Schema:
  users: id, email, password_hash, tier, pro_expires_at, created_at
  transcription_history: id, user_id, task_id, original_filename, engine, created_at
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import BASE_DIR

DB_PATH = BASE_DIR / "note_digger.db"

# Free trial limits
FREE_TRIAL_LIMIT = 3


def _get_db() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    """Create tables if they don't exist."""
    db = _get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            tier TEXT NOT NULL DEFAULT 'free',
            pro_expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transcription_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            original_filename TEXT,
            engine TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS activation_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            duration_days INTEGER NOT NULL DEFAULT 30,
            used_by INTEGER,
            used_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (used_by) REFERENCES users(id)
        );
    """)
    db.commit()
    db.close()


def hash_password(password: str) -> str:
    """Hash a password with SHA-256 + salt."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    salt, h = password_hash.split("$", 1)
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == h


def create_user(email: str, password: str) -> dict:
    """Create a new user. Returns user dict or raises ValueError."""
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("请输入有效的邮箱地址")
    if len(password) < 6:
        raise ValueError("密码至少需要6个字符")

    db = _get_db()
    try:
        pw_hash = hash_password(password)
        cursor = db.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, pw_hash),
        )
        db.commit()
        user_id = cursor.lastrowid
        return {"id": user_id, "email": email, "tier": "free", "pro_expires_at": None}
    except sqlite3.IntegrityError:
        raise ValueError("该邮箱已注册")
    finally:
        db.close()


def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Authenticate user by email + password. Returns user dict or None."""
    email = email.strip().lower()
    db = _get_db()
    try:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return dict(row)
        return None
    finally:
        db.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    db = _get_db()
    try:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def get_free_usage_count(user_id: int) -> int:
    """Count how many transcriptions this user has done (for free tier limiting)."""
    db = _get_db()
    try:
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM transcription_history WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["cnt"]
    finally:
        db.close()


def can_transcribe(user_id: int) -> tuple[bool, str]:
    """Check if user can transcribe. Returns (allowed, reason)."""
    user = get_user_by_id(user_id)
    if not user:
        return False, "用户不存在"

    if user["tier"] == "pro":
        # Check if pro has expired
        if user["pro_expires_at"]:
            expires = datetime.fromisoformat(user["pro_expires_at"])
            if expires < datetime.now(timezone.utc):
                return True, "pro_expired"  # Grace period: still allow
        return True, "pro"

    # Free tier
    count = get_free_usage_count(user_id)
    if count >= FREE_TRIAL_LIMIT:
        return False, f"免费试用已达上限（{FREE_TRIAL_LIMIT}次），请升级 Pro"
    return True, f"free_{count + 1}/{FREE_TRIAL_LIMIT}"


def record_transcription(user_id: int, task_id: str, filename: str = "", engine: str = "") -> bool:
    """Record a transcription in user history. Returns True on success."""
    db = _get_db()
    try:
        db.execute(
            "INSERT INTO transcription_history (user_id, task_id, original_filename, engine) VALUES (?, ?, ?, ?)",
            (user_id, task_id, filename, engine),
        )
        db.commit()
        return True
    except Exception:
        return False
    finally:
        db.close()


def get_user_history(user_id: int, limit: int = 50) -> list[dict]:
    """Get user's transcription history."""
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT * FROM transcription_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


def activate_pro(user_id: int, code: str) -> tuple[bool, str]:
    """Activate Pro tier with an activation code. Returns (success, message)."""
    db = _get_db()
    try:
        row = db.execute(
            "SELECT * FROM activation_codes WHERE code = ? AND used_by IS NULL",
            (code,),
        ).fetchone()
        if not row:
            return False, "激活码无效或已被使用"

        duration = row["duration_days"]
        db.execute(
            "UPDATE activation_codes SET used_by = ?, used_at = datetime('now') WHERE id = ?",
            (user_id, row["id"]),
        )

        # Calculate expiry
        from datetime import datetime as dt, timedelta
        expires = dt.now(timezone.utc) + timedelta(days=duration)
        db.execute(
            "UPDATE users SET tier = 'pro', pro_expires_at = ? WHERE id = ?",
            (expires.isoformat(), user_id),
        )
        db.commit()
        return True, f"Pro 已激活！有效期至 {expires.strftime('%Y-%m-%d')}"
    finally:
        db.close()


def generate_activation_codes(count: int = 10, duration_days: int = 30) -> list[str]:
    """Generate activation codes. Returns list of codes."""
    db = _get_db()
    codes = []
    try:
        for _ in range(count):
            code = f"ND-{secrets.token_hex(4).upper()}"
            db.execute(
                "INSERT INTO activation_codes (code, duration_days) VALUES (?, ?)",
                (code, duration_days),
            )
            codes.append(code)
        db.commit()
    finally:
        db.close()
    return codes


# Initialize DB on import
init_db()
