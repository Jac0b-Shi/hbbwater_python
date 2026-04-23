"""Account profile and user management routes."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_control_db
from app.services.account import account_service
from app.services.auth import get_current_user, require_roles

router = APIRouter(prefix="/account", tags=["account"])
require_super_admin = require_roles("super_admin")


class AccountProfileResponse(BaseModel):
    id: str
    username: str
    display_name: str
    email: EmailStr
    phone: str = ""
    role: str
    role_label: str
    permissions: list[str]
    auth_provider: str
    auth_provider_label: str
    avatar_hash: str
    avatar_url: str
    created_at: datetime
    updated_at: datetime
    can_update_profile: bool
    can_change_password: bool
    password_initialized: bool
    is_active: bool


class AccountProfileUpdate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    phone: str = Field(default="", max_length=32)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(default="", max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AdminUserResponse(AccountProfileResponse):
    pass


class AdminUserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    phone: str = Field(default="", max_length=32)
    role: Optional[str] = Field(default="user", max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=2, max_length=50)
    display_name: Optional[str] = Field(default=None, min_length=2, max_length=50)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=32)
    role: Optional[str] = Field(default=None, max_length=50)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    is_active: Optional[bool] = None


@router.get("/me", response_model=AccountProfileResponse)
async def get_current_account(
    current_user: dict = Depends(get_current_user),
):
    """Return the current authenticated account profile."""
    return AccountProfileResponse(**current_user)


@router.put("/me", response_model=AccountProfileResponse)
async def update_current_account(
    payload: AccountProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_control_db),
):
    """Update the current user's own profile."""
    profile = await account_service.update_profile(db, payload.model_dump(), user_id=int(current_user["id"]))
    return AccountProfileResponse(**profile)


@router.post("/me/password")
async def change_current_password(
    payload: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_control_db),
):
    """Change the current user's local password."""
    await account_service.change_password(
        db,
        payload.current_password,
        payload.new_password,
        user_id=int(current_user["id"]),
    )
    return {"message": "密码已更新"}


@router.get("/providers")
async def get_account_providers(
    _: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_control_db),
):
    """List supported authentication providers."""
    return await account_service.get_provider_catalog(db)


@router.get("/roles")
async def get_account_roles(_: dict = Depends(get_current_user)):
    """List available role definitions for the UI."""
    return {"roles": await account_service.get_roles_catalog()}


@router.get("/admin-users", response_model=list[AdminUserResponse])
async def list_admin_users(
    _: dict = Depends(require_super_admin),
    db: AsyncSession = Depends(get_control_db),
):
    """List all local users for super-admin management."""
    users = await account_service.list_users(db)
    return [AdminUserResponse(**user) for user in users]


@router.post("/admin-users", response_model=AdminUserResponse, status_code=201)
async def create_admin_user(
    payload: AdminUserCreate,
    _: dict = Depends(require_super_admin),
    db: AsyncSession = Depends(get_control_db),
):
    """Create a local user directly from the user-management screen."""
    user = await account_service.create_user(db, payload.model_dump())
    return AdminUserResponse(**user)


@router.patch("/admin-users/{user_id}", response_model=AdminUserResponse)
async def update_admin_user(
    user_id: int,
    payload: AdminUserUpdate,
    current_user: dict = Depends(require_super_admin),
    db: AsyncSession = Depends(get_control_db),
):
    """Update another user's role, status, or basic info."""
    user = await account_service.update_user(
        db,
        user_id=user_id,
        payload=payload.model_dump(exclude_unset=True),
        actor_user_id=int(current_user["id"]),
    )
    return AdminUserResponse(**user)
