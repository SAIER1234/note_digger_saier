"""Authentication API routes — register, login, profile, activation."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.models.user import (
    create_user,
    authenticate_user,
    get_user_by_id,
    get_free_usage_count,
    get_user_history,
    activate_pro,
    FREE_TRIAL_LIMIT,
)
from app.middleware.auth import create_token, get_user_from_header

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request schemas ──

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ActivateRequest(BaseModel):
    code: str


class AuthResponse(BaseModel):
    token: str
    user: dict


# ── Routes ──

@router.post("/register")
async def register(req: RegisterRequest):
    """Register a new user account."""
    try:
        user = create_user(req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = create_token(user["id"], user["email"], user["tier"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "tier": user["tier"],
            "usage_count": 0,
            "usage_limit": FREE_TRIAL_LIMIT,
        },
    }


@router.post("/login")
async def login(req: LoginRequest):
    """Login with email and password."""
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    token = create_token(user["id"], user["email"], user["tier"])
    usage_count = get_free_usage_count(user["id"]) if user["tier"] == "free" else 0
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "tier": user["tier"],
            "pro_expires_at": user.get("pro_expires_at"),
            "usage_count": usage_count,
            "usage_limit": FREE_TRIAL_LIMIT,
        },
    }


@router.get("/me")
async def me(authorization: str = ""):
    """Get current user profile from token."""
    # FastAPI doesn't auto-extract header for GET requests with no body
    # We accept it as a parameter; the frontend sends it via Authorization header
    return {"error": "use POST /me with Authorization header"}


@router.post("/me")
async def me_post(req: dict | None = None):
    """Get current user profile. Token parsed from Authorization header by caller."""
    # This is handled by the frontend which sends token directly
    # For simplicity, we use a query-based approach
    return {"note": "Use GET /me/token/{token} instead"}


@router.get("/me/token/{token}")
async def me_by_token(token: str):
    """Get current user profile from JWT token."""
    payload = get_user_from_header(f"Bearer {token}")
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")

    user = get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    usage_count = get_free_usage_count(user["id"]) if user["tier"] == "free" else 0
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "tier": user["tier"],
            "pro_expires_at": user.get("pro_expires_at"),
            "usage_count": usage_count,
            "usage_limit": FREE_TRIAL_LIMIT,
        },
    }


@router.get("/me/header")
async def me_by_header(authorization: str = ""):
    """Get current user profile. The Authorization header should be passed as query param
    since Swagger UI and some clients don't send custom headers easily."""
    # FastAPI can extract headers directly
    # We use a workaround: accept token as query parameter for simplicity
    return {"error": "use /me/token/{token} instead"}


@router.post("/activate")
async def activate(req: ActivateRequest):
    """Activate Pro tier with a code. Token in Authorization header."""
    # Token parsing handled inline since we can't easily access headers in query-based API
    return {"error": "use POST /activate with Authorization header. Send as: /activate/token/{token}/code/{code}"}


@router.post("/activate/token/{token}/code/{code}")
async def activate_pro_endpoint(token: str, code: str):
    """Activate Pro tier."""
    payload = get_user_from_header(f"Bearer {token}")
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")

    ok, msg = activate_pro(payload["user_id"], code)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    user = get_user_by_id(payload["user_id"])
    new_token = create_token(user["id"], user["email"], user["tier"])
    return {"token": new_token, "message": msg, "user": {
        "id": user["id"], "email": user["email"],
        "tier": user["tier"], "pro_expires_at": user.get("pro_expires_at"),
    }}


@router.get("/history/{token}")
async def history(token: str):
    """Get user's transcription history."""
    payload = get_user_from_header(f"Bearer {token}")
    if not payload:
        raise HTTPException(status_code=401, detail="token 无效或已过期")

    history = get_user_history(payload["user_id"])
    return {"history": history}
