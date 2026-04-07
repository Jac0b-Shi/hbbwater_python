"""Account domain services with pluggable identity providers."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterable

from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser, SystemConfig

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

LOCAL_ACCOUNT_DEFAULTS = {
    "account_provider": ("local", "当前账户认证提供者"),
    "account_local_user_id": ("1", "本地账户用户ID"),
    "account_local_username": ("admin", "本地账户登录名"),
    "account_local_display_name": ("管理员", "本地账户显示名称"),
    "account_local_email": ("admin@example.com", "本地账户邮箱"),
    "account_local_phone": ("", "本地账户手机号"),
    "account_local_role": ("系统管理员", "本地账户角色"),
    "account_local_password_hash": ("", "本地账户密码哈希"),
    "account_local_created_at": ("2024-01-01T00:00:00", "本地账户创建时间"),
}

PROVIDER_DEFINITIONS = {
    "local": {
        "id": "local",
        "label": "本地账户",
        "enabled": True,
        "supports_password": True,
        "supports_profile_edit": True,
        "supports_avatar": True,
        "supports_sso_binding": False,
    },
    "campus_sso": {
        "id": "campus_sso",
        "label": "校园统一身份认证",
        "enabled": False,
        "supports_password": False,
        "supports_profile_edit": False,
        "supports_avatar": True,
        "supports_sso_binding": True,
    },
}


async def get_config_rows(db: AsyncSession, keys: Iterable[str]) -> list[SystemConfig]:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key.in_(list(keys)))
    )
    return list(result.scalars().all())


async def get_config_map(db: AsyncSession, defaults: dict[str, tuple[str, str]]) -> dict[str, str]:
    rows = await get_config_rows(db, defaults.keys())
    row_map = {row.config_key: row for row in rows}

    for key, (value, description) in defaults.items():
        if key not in row_map:
            row = SystemConfig(
                config_key=key,
                config_value=value,
                description=description,
            )
            db.add(row)
            row_map[key] = row

    await db.flush()
    return {
        key: (row_map[key].config_value or "")
        for key in defaults
    }


async def set_config_value(db: AsyncSession, key: str, value: str, description: str = "") -> None:
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    config = result.scalar_one_or_none()
    if config:
        config.config_value = value
        if description:
            config.description = description
        config.updated_at = datetime.utcnow()
        return

    db.add(
        SystemConfig(
            config_key=key,
            config_value=value,
            description=description,
        )
    )
    await db.flush()


def build_gravatar(email: str, size: int = 256) -> dict[str, str]:
    normalized = (email or "").strip().lower()
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    return {
        "avatar_hash": digest,
        "avatar_url": f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}",
    }


class AccountProvider(ABC):
    provider_id: str

    @abstractmethod
    async def get_profile(self, db: AsyncSession, username: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def list_users(self, db: AsyncSession) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def create_user(self, db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def update_profile(self, db: AsyncSession, payload: dict[str, Any], username: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def change_password(self, db: AsyncSession, current_password: str, new_password: str, username: str | None = None) -> None:
        raise NotImplementedError


class LocalAccountProvider(AccountProvider):
    provider_id = "local"

    async def _get_or_bootstrap_user(self, db: AsyncSession, username: str | None = None) -> AdminUser:
        await get_config_map(db, LOCAL_ACCOUNT_DEFAULTS)

        query = select(AdminUser).where(AdminUser.is_active == True)
        if username:
            query = query.where(AdminUser.username == username)
        query = query.order_by(AdminUser.id.asc())

        result = await db.execute(query)
        user = result.scalar_one_or_none()
        if user:
            return user

        bootstrap_user = AdminUser(
            username="admin",
            display_name="管理员",
            email="admin@example.com",
            phone="",
            role="系统管理员",
            auth_provider=self.provider_id,
            is_active=True,
        )
        db.add(bootstrap_user)
        await db.commit()
        await db.refresh(bootstrap_user)
        return bootstrap_user

    def _serialize_user(self, user: AdminUser) -> dict[str, Any]:
        gravatar = build_gravatar(user.email)
        return {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name or user.username,
            "email": user.email,
            "phone": user.phone or "",
            "role": user.role or "管理员",
            "auth_provider": user.auth_provider or self.provider_id,
            "auth_provider_label": PROVIDER_DEFINITIONS[self.provider_id]["label"],
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
            "can_update_profile": True,
            "can_change_password": True,
            "password_initialized": bool(user.password_hash),
            **gravatar,
        }

    async def get_profile(self, db: AsyncSession, username: str | None = None) -> dict[str, Any]:
        user = await self._get_or_bootstrap_user(db, username=username)
        return self._serialize_user(user)

    async def list_users(self, db: AsyncSession) -> list[dict[str, Any]]:
        result = await db.execute(select(AdminUser).order_by(AdminUser.id.asc()))
        users = result.scalars().all()
        return [self._serialize_user(user) | {"is_active": user.is_active} for user in users]

    async def create_user(self, db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        user = AdminUser(
            username=payload["username"].strip(),
            display_name=payload["display_name"].strip(),
            email=payload["email"].strip().lower(),
            phone=(payload.get("phone") or "").strip(),
            role=(payload.get("role") or "系统管理员").strip(),
            auth_provider=self.provider_id,
            is_active=payload.get("is_active", True),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return self._serialize_user(user) | {"is_active": user.is_active}

    async def update_profile(self, db: AsyncSession, payload: dict[str, Any], username: str | None = None) -> dict[str, Any]:
        user = await self._get_or_bootstrap_user(db, username=username)
        for field in ("username", "display_name", "email", "phone", "role"):
            if field in payload and payload[field] is not None:
                value = str(payload[field]).strip()
                if field == "email":
                    value = value.lower()
                setattr(user, field, value)

        await db.commit()
        await db.refresh(user)
        return self._serialize_user(user)

    async def change_password(self, db: AsyncSession, current_password: str, new_password: str, username: str | None = None) -> None:
        user = await self._get_or_bootstrap_user(db, username=username)
        password_hash = user.password_hash or ""

        if password_hash and not pwd_context.verify(current_password, password_hash):
            raise HTTPException(status_code=400, detail="当前密码错误")

        user.password_hash = pwd_context.hash(new_password)
        await db.commit()


class UnsupportedAccountProvider(AccountProvider):
    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    async def get_profile(self, db: AsyncSession, username: str | None = None) -> dict[str, Any]:
        raise HTTPException(status_code=501, detail=f"账户提供者 {self.provider_id} 尚未实现")

    async def list_users(self, db: AsyncSession) -> list[dict[str, Any]]:
        raise HTTPException(status_code=501, detail=f"账户提供者 {self.provider_id} 尚未实现")

    async def create_user(self, db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        raise HTTPException(status_code=501, detail=f"账户提供者 {self.provider_id} 尚未实现")

    async def update_profile(self, db: AsyncSession, payload: dict[str, Any], username: str | None = None) -> dict[str, Any]:
        raise HTTPException(status_code=501, detail=f"账户提供者 {self.provider_id} 尚未实现")

    async def change_password(self, db: AsyncSession, current_password: str, new_password: str, username: str | None = None) -> None:
        raise HTTPException(status_code=501, detail=f"账户提供者 {self.provider_id} 尚未实现")


class AccountService:
    async def get_provider_id(self, db: AsyncSession) -> str:
        config = await get_config_map(db, {"account_provider": LOCAL_ACCOUNT_DEFAULTS["account_provider"]})
        return config["account_provider"] or "local"

    async def get_provider(self, db: AsyncSession) -> AccountProvider:
        provider_id = await self.get_provider_id(db)
        if provider_id == "local":
            return LocalAccountProvider()
        return UnsupportedAccountProvider(provider_id)

    async def get_profile(self, db: AsyncSession, username: str | None = None) -> dict[str, Any]:
        provider = await self.get_provider(db)
        return await provider.get_profile(db, username=username)

    async def list_users(self, db: AsyncSession) -> list[dict[str, Any]]:
        provider = await self.get_provider(db)
        return await provider.list_users(db)

    async def create_user(self, db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        provider = await self.get_provider(db)
        return await provider.create_user(db, payload)

    async def update_profile(self, db: AsyncSession, payload: dict[str, Any], username: str | None = None) -> dict[str, Any]:
        provider = await self.get_provider(db)
        return await provider.update_profile(db, payload, username=username)

    async def change_password(self, db: AsyncSession, current_password: str, new_password: str, username: str | None = None) -> None:
        provider = await self.get_provider(db)
        await provider.change_password(db, current_password, new_password, username=username)

    async def get_provider_catalog(self, db: AsyncSession) -> dict[str, Any]:
        current = await self.get_provider_id(db)
        return {
            "current": current,
            "providers": list(PROVIDER_DEFINITIONS.values()),
        }


account_service = AccountService()
