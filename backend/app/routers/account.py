"""Account router with provider-aware interfaces."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_control_db
from app.services.account import account_service

router = APIRouter(prefix="/account", tags=["account"])


class AccountProfileResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: EmailStr
    phone: str = ""
    role: str
    auth_provider: str
    auth_provider_label: str
    avatar_hash: str
    avatar_url: str
    created_at: datetime
    updated_at: datetime
    can_update_profile: bool
    can_change_password: bool
    password_initialized: bool


class AccountProfileUpdate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    phone: str = Field(default="", max_length=32)
    role: Optional[str] = Field(default=None, max_length=50)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(default="", max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminUserResponse(AccountProfileResponse):
    is_active: bool


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    phone: str = Field(default="", max_length=32)
    role: Optional[str] = Field(default="系统管理员", max_length=50)
    is_active: bool = True


@router.get("/me", response_model=AccountProfileResponse)
async def get_current_account(
    x_account_username: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_control_db),
):
    """Get current account profile."""
    profile = await account_service.get_profile(db, username=x_account_username)
    return AccountProfileResponse(**profile)


@router.put("/me", response_model=AccountProfileResponse)
async def update_current_account(
    payload: AccountProfileUpdate,
    x_account_username: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_control_db),
):
    """Update current account profile."""
    cleaned_payload = payload.model_dump()
    cleaned_payload["phone"] = cleaned_payload["phone"].strip()
    cleaned_payload["role"] = (cleaned_payload.get("role") or "").strip() or None

    profile = await account_service.update_profile(db, cleaned_payload, username=x_account_username)
    return AccountProfileResponse(**profile)


@router.post("/me/password")
async def change_current_password(
    payload: PasswordChangeRequest,
    x_account_username: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_control_db),
):
    """Change current account password."""
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    await account_service.change_password(db, payload.current_password, payload.new_password, username=x_account_username)
    return {"message": "密码已更新"}


@router.get("/providers")
async def get_account_providers(db: AsyncSession = Depends(get_control_db)):
    """List supported account providers for future auth integrations."""
    return await account_service.get_provider_catalog(db)


@router.get("/admin-users", response_model=list[AdminUserResponse])
async def list_admin_users(db: AsyncSession = Depends(get_control_db)):
    """List local admin users as the basis for multi-admin expansion."""
    users = await account_service.list_users(db)
    return [AdminUserResponse(**user) for user in users]


@router.post("/admin-users", response_model=AdminUserResponse, status_code=201)
async def create_admin_user(
    payload: AdminUserCreate,
    db: AsyncSession = Depends(get_control_db),
):
    """Create a local admin user."""
    user = await account_service.create_user(db, payload.model_dump())
    return AdminUserResponse(**user)
