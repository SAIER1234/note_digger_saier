"""JWT authentication utilities."""

import hashlib
import hmac
import json
import time
import secrets
from typing import Optional

# In production, use a persistent secret. For now, derive from hostname.
# This means tokens survive restarts but are unique per machine.
JWT_SECRET = secrets.token_hex(32)  # Rotates on restart — acceptable for MVP


def create_token(user_id: int, email: str, tier: str) -> str:
    """Create a simple signed JWT-like token."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "user_id": user_id,
        "email": email,
        "tier": tier,
        "iat": int(time.time()),
        "exp": int(time.time()) + 30 * 24 * 3600,  # 30 days
    }

    def _b64(data: bytes) -> str:
        import base64
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    h = _b64(json.dumps(header).encode())
    p = _b64(json.dumps(payload).encode())
    msg = f"{h}.{p}"
    sig = hmac.new(JWT_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a token. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h, p, sig = parts

        import base64
        def _deb64(s: str) -> bytes:
            s += "=" * (4 - len(s) % 4)
            return base64.urlsafe_b64decode(s)

        msg = f"{h}.{p}"
        expected = hmac.new(JWT_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None

        payload = json.loads(_deb64(p))
        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception:
        return None


def get_user_from_header(authorization: Optional[str]) -> Optional[dict]:
    """Extract user from Authorization: Bearer <token> header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    return decode_token(token)
