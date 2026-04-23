"""Authentication routes for login and email-verified registration."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_control_db
from app.services.account import account_service
from app.services.auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    login: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class RegisterCodeRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    verification_code: str | None = Field(default=None, min_length=4, max_length=12)
    password: str = Field(..., min_length=8, max_length=128)


@router.post("/login")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_control_db),
):
    """Authenticate with local credentials and return a bearer token."""
    user = await account_service.authenticate(db, payload.login, payload.password)
    token, expires_in = create_access_token(user)
    return {
        "message": "登录成功",
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user,
    }


@router.post("/register/request-code")
async def request_register_code(
    payload: RegisterCodeRequest,
    db: AsyncSession = Depends(get_control_db),
):
    """Send an email verification code for self-registration."""
    return await account_service.request_registration_code(db, payload.email)


@router.get("/registration-status")
async def get_registration_status(db: AsyncSession = Depends(get_control_db)):
    """Expose whether self-registration currently requires email verification."""
    return await account_service.get_registration_status(db)


@router.post("/register")
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_control_db),
):
    """Register a new local user.

    The first local account bootstraps the system and is signed in immediately.
    Later self-registered accounts remain inactive until a super admin enables them.
    """
    user = await account_service.register_user(db, payload.model_dump())
    if not user.get("is_active"):
        return {
            "message": "注册成功，账号默认停用，请联系超级管理员开通账号权限后再登录",
            "requires_activation": True,
            "access_token": None,
            "token_type": "bearer",
            "expires_in": 0,
            "user": user,
        }

    token, expires_in = create_access_token(user)
    return {
        "message": "注册成功",
        "requires_activation": False,
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user,
    }


@router.post("/logout")
async def logout():
    """Frontend-managed logout placeholder."""
    return {"message": "已退出登录"}
