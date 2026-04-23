"""Account, registration, and role management services."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import string
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser, SystemConfig

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_USER = "user"

ROLE_DEFINITIONS = {
    ROLE_SUPER_ADMIN: {
        "id": ROLE_SUPER_ADMIN,
        "label": "超级管理员",
        "description": "管理用户、分配权限、访问系统设置，并拥有全部业务操作权限",
        "permissions": ["settings:write", "users:write", "sensors:write", "alerts:resolve"],
    },
    ROLE_ADMIN: {
        "id": ROLE_ADMIN,
        "label": "管理员",
        "description": "管理传感器和处理告警，但不能访问系统设置和用户权限分配",
        "permissions": ["sensors:write", "alerts:resolve"],
    },
    ROLE_USER: {
        "id": ROLE_USER,
        "label": "用户",
        "description": "仅查看监测数据、告警和个人资料",
        "permissions": [],
    },
}

ROLE_ALIASES = {
    "super_admin": ROLE_SUPER_ADMIN,
    "超级管理员": ROLE_SUPER_ADMIN,
    "系统管理员": ROLE_SUPER_ADMIN,
    "admin": ROLE_ADMIN,
    "管理员": ROLE_ADMIN,
    "user": ROLE_USER,
    "viewer": ROLE_USER,
    "普通用户": ROLE_USER,
    "用户": ROLE_USER,
}

LOCAL_ACCOUNT_DEFAULTS = {
    "account_provider": ("local", "当前账户认证提供者"),
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

REGISTRATION_CODE_TTL_MINUTES = int(os.getenv("REGISTRATION_CODE_TTL_MINUTES", "10"))
REGISTRATION_CODE_COOLDOWN_SECONDS = int(os.getenv("REGISTRATION_CODE_COOLDOWN_SECONDS", "60"))
PASSWORD_MIN_LENGTH = 8
BCRYPT_PASSWORD_MAX_BYTES = 72
BCRYPT_PASSWORD_TOO_LONG_MESSAGE = "密码不能超过 72 字节，中文和特殊字符会占用更多字节"


def normalize_role(role: str | None) -> str:
    """Normalize user-facing or legacy role labels into stable role codes."""
    if role is None:
        return ROLE_USER

    value = str(role).strip()
    if not value:
        return ROLE_USER

    lowered = value.lower()
    if lowered in ROLE_DEFINITIONS:
        return lowered
    return ROLE_ALIASES.get(value) or ROLE_ALIASES.get(lowered) or ROLE_USER


def parse_role(role: str | None, default: str = ROLE_USER) -> str:
    """Validate a role selection and raise if the provided value is unknown."""
    if role is None:
        return default

    value = str(role).strip()
    if not value:
        return default

    normalized = normalize_role(value)
    if value.lower() not in ROLE_DEFINITIONS and value not in ROLE_ALIASES and value.lower() not in ROLE_ALIASES:
        raise HTTPException(status_code=400, detail="无效的角色类型")
    return normalized


def has_any_role(role: str | None, allowed_roles: tuple[str, ...] | list[str]) -> bool:
    normalized = normalize_role(role)
    return normalized in {normalize_role(item) for item in allowed_roles}


def build_gravatar(email: str, size: int = 256) -> dict[str, str]:
    normalized = (email or "").strip().lower()
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    return {
        "avatar_hash": digest,
        "avatar_url": f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}",
    }


def _registration_key(email: str) -> str:
    digest = hashlib.sha1(email.encode("utf-8")).hexdigest()
    return f"auth_register_code:{digest}"


def _hash_registration_code(email: str, code: str) -> str:
    secret = os.getenv("APP_SECRET_KEY", "").strip() or os.getenv("INTERNAL_API_TOKEN", "").strip() or "hbbwater-registration"
    source = f"{email.lower()}:{code.strip()}:{secret}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _get_password_byte_length(password: str) -> int:
    return len((password or "").encode("utf-8"))


def _validate_password(password: str, minimum_message: str | None = None) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=minimum_message or f"密码长度不能少于 {PASSWORD_MIN_LENGTH} 位",
        )
    if _get_password_byte_length(password) > BCRYPT_PASSWORD_MAX_BYTES:
        raise HTTPException(status_code=400, detail=BCRYPT_PASSWORD_TOO_LONG_MESSAGE)


def _hash_password(password: str, minimum_message: str | None = None) -> str:
    _validate_password(password, minimum_message=minimum_message)
    try:
        return pwd_context.hash(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=BCRYPT_PASSWORD_TOO_LONG_MESSAGE) from exc


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        return False


async def get_config_rows(db: AsyncSession, keys: list[str]) -> list[SystemConfig]:
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key.in_(keys)))
    return list(result.scalars().all())


async def get_config_map(db: AsyncSession, defaults: dict[str, tuple[str, str]]) -> dict[str, str]:
    rows = await get_config_rows(db, list(defaults.keys()))
    row_map = {row.config_key: row for row in rows}
    inserted_any = False

    for key, (value, description) in defaults.items():
        if key not in row_map:
            try:
                async with db.begin_nested():
                    db.add(
                        SystemConfig(
                            config_key=key,
                            config_value=value,
                            description=description,
                        )
                    )
                    await db.flush()
                inserted_any = True
            except IntegrityError:
                continue

    if inserted_any:
        await db.commit()
        rows = await get_config_rows(db, list(defaults.keys()))
        row_map = {row.config_key: row for row in rows}

    return {
        key: (row_map[key].config_value or "") if key in row_map else value
        for key, (value, _) in defaults.items()
    }


async def set_config_value(db: AsyncSession, key: str, value: str, description: str = "") -> None:
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    config = result.scalar_one_or_none()
    if config:
        config.config_value = value
        if description:
            config.description = description
        config.updated_at = datetime.utcnow()
        await db.flush()
        return

    db.add(
        SystemConfig(
            config_key=key,
            config_value=value,
            description=description,
        )
    )
    await db.flush()


class AccountService:
    def serialize_user(self, user: AdminUser) -> dict[str, Any]:
        role_code = normalize_role(user.role)
        role_definition = ROLE_DEFINITIONS[role_code]
        gravatar = build_gravatar(user.email)
        return {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name or user.username,
            "email": user.email,
            "phone": user.phone or "",
            "role": role_code,
            "role_label": role_definition["label"],
            "permissions": list(role_definition["permissions"]),
            "auth_provider": user.auth_provider or "local",
            "auth_provider_label": PROVIDER_DEFINITIONS.get(user.auth_provider or "local", PROVIDER_DEFINITIONS["local"])["label"],
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
            "can_update_profile": True,
            "can_change_password": True,
            "password_initialized": bool(user.password_hash),
            "is_active": bool(user.is_active),
            **gravatar,
        }

    async def ensure_bootstrap(self, db: AsyncSession) -> None:
        """Ensure control-plane defaults and a placeholder super admin exist."""
        await get_config_map(db, LOCAL_ACCOUNT_DEFAULTS)

        result = await db.execute(select(AdminUser).order_by(AdminUser.id.asc()))
        users = result.scalars().all()
        if users:
            if not any(normalize_role(user.role) == ROLE_SUPER_ADMIN and user.is_active for user in users):
                users[0].role = ROLE_SUPER_ADMIN
                users[0].is_active = True
                await db.commit()
            return

        bootstrap_user = AdminUser(
            username="admin",
            display_name="超级管理员",
            email="admin@example.com",
            phone="",
            role=ROLE_SUPER_ADMIN,
            auth_provider="local",
            is_active=True,
        )
        db.add(bootstrap_user)
        await db.commit()

    async def get_provider_id(self, db: AsyncSession) -> str:
        config = await get_config_map(db, LOCAL_ACCOUNT_DEFAULTS)
        return config["account_provider"] or "local"

    async def get_provider_catalog(self, db: AsyncSession) -> dict[str, Any]:
        current = await self.get_provider_id(db)
        return {
            "current": current,
            "providers": list(PROVIDER_DEFINITIONS.values()),
        }

    async def get_roles_catalog(self) -> list[dict[str, Any]]:
        return [ROLE_DEFINITIONS[item] for item in (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_USER)]

    async def _get_user_by_id(self, db: AsyncSession, user_id: int) -> AdminUser | None:
        result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
        return result.scalar_one_or_none()

    async def _get_user_by_username(self, db: AsyncSession, username: str) -> AdminUser | None:
        result = await db.execute(select(AdminUser).where(func.lower(AdminUser.username) == username.lower()))
        return result.scalar_one_or_none()

    async def _get_user_by_email(self, db: AsyncSession, email: str) -> AdminUser | None:
        result = await db.execute(select(AdminUser).where(func.lower(AdminUser.email) == email.lower()))
        return result.scalar_one_or_none()

    async def _get_user_by_login(self, db: AsyncSession, login: str) -> AdminUser | None:
        normalized = login.strip().lower()
        result = await db.execute(
            select(AdminUser).where(
                or_(
                    func.lower(AdminUser.username) == normalized,
                    func.lower(AdminUser.email) == normalized,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _ensure_unique_identity(
        self,
        db: AsyncSession,
        *,
        username: str,
        email: str,
        exclude_user_id: int | None = None,
    ) -> None:
        query = select(AdminUser).where(
            or_(
                func.lower(AdminUser.username) == username.lower(),
                func.lower(AdminUser.email) == email.lower(),
            )
        )
        result = await db.execute(query)
        conflicts = result.scalars().all()

        for user in conflicts:
            if exclude_user_id and user.id == exclude_user_id:
                continue
            if user.username.lower() == username.lower():
                raise HTTPException(status_code=400, detail="登录名已存在")
            if user.email.lower() == email.lower():
                raise HTTPException(status_code=400, detail="邮箱已被使用")

    async def _count_active_super_admins(self, db: AsyncSession) -> int:
        result = await db.execute(select(AdminUser))
        users = result.scalars().all()
        return sum(1 for user in users if user.is_active and normalize_role(user.role) == ROLE_SUPER_ADMIN)

    async def _first_usable_super_admin_exists(self, db: AsyncSession) -> bool:
        result = await db.execute(select(AdminUser))
        users = result.scalars().all()
        return any(
            user.is_active and bool(user.password_hash) and normalize_role(user.role) == ROLE_SUPER_ADMIN
            for user in users
        )

    async def get_registration_status(self, db: AsyncSession) -> dict[str, Any]:
        """Return whether self-registration currently requires email verification."""
        requires_email_verification = await self._first_usable_super_admin_exists(db)
        return {
            "bootstrap_mode": not requires_email_verification,
            "requires_email_verification": requires_email_verification,
        }

    async def _disable_placeholder_bootstrap_admin(self, db: AsyncSession) -> None:
        result = await db.execute(
            select(AdminUser).where(
                AdminUser.username == "admin",
                AdminUser.email == "admin@example.com",
                AdminUser.password_hash == "",
            )
        )
        placeholder = result.scalar_one_or_none()
        if placeholder and placeholder.is_active:
            placeholder.is_active = False
            await db.flush()

    async def get_profile(self, db: AsyncSession, user_id: int | None = None) -> dict[str, Any]:
        await self.ensure_bootstrap(db)

        user: AdminUser | None = None
        if user_id is not None:
            user = await self._get_user_by_id(db, user_id)
        if user is None:
            result = await db.execute(select(AdminUser).where(AdminUser.is_active == True).order_by(AdminUser.id.asc()))
            user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=404, detail="账户不存在或已停用")

        return self.serialize_user(user)

    async def list_users(self, db: AsyncSession) -> list[dict[str, Any]]:
        result = await db.execute(select(AdminUser).order_by(AdminUser.created_at.asc(), AdminUser.id.asc()))
        users = result.scalars().all()
        return [self.serialize_user(user) for user in users]

    async def create_user(self, db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        username = payload["username"].strip()
        display_name = (payload.get("display_name") or username).strip()
        email = payload["email"].strip().lower()
        phone = (payload.get("phone") or "").strip()
        role = parse_role(payload.get("role"), default=ROLE_USER)
        password = str(payload.get("password") or "")

        await self._ensure_unique_identity(db, username=username, email=email)

        user = AdminUser(
            username=username,
            display_name=display_name,
            email=email,
            phone=phone,
            role=role,
            password_hash=_hash_password(password, minimum_message="初始密码长度不能少于 8 位"),
            auth_provider="local",
            is_active=bool(payload.get("is_active", True)),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return self.serialize_user(user)

    async def update_user(self, db: AsyncSession, user_id: int, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
        user = await self._get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        original_role = normalize_role(user.role)
        next_role = original_role
        if "role" in payload and payload["role"] is not None:
            next_role = parse_role(payload["role"], default=original_role)

        next_is_active = user.is_active if payload.get("is_active") is None else bool(payload["is_active"])

        if actor_user_id == user.id:
            if next_role != original_role:
                raise HTTPException(status_code=400, detail="不能修改自己的角色，请由其他超级管理员操作")
            if not next_is_active:
                raise HTTPException(status_code=400, detail="不能停用当前登录账号")

        if original_role == ROLE_SUPER_ADMIN and (next_role != ROLE_SUPER_ADMIN or not next_is_active):
            if await self._count_active_super_admins(db) <= 1:
                raise HTTPException(status_code=400, detail="系统至少需要保留一个启用状态的超级管理员")

        username = (payload.get("username") or user.username).strip()
        email = (payload.get("email") or user.email).strip().lower()
        await self._ensure_unique_identity(db, username=username, email=email, exclude_user_id=user.id)

        user.username = username
        user.display_name = (payload.get("display_name") or user.display_name or username).strip()
        user.email = email
        user.phone = (payload.get("phone") if payload.get("phone") is not None else user.phone or "").strip()
        user.role = next_role
        user.is_active = next_is_active

        password = str(payload.get("password") or "").strip()
        if password:
            user.password_hash = _hash_password(password)

        await db.commit()
        await db.refresh(user)
        return self.serialize_user(user)

    async def update_profile(self, db: AsyncSession, payload: dict[str, Any], user_id: int) -> dict[str, Any]:
        user = await self._get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=404, detail="账户不存在或已停用")

        username = payload["username"].strip()
        email = payload["email"].strip().lower()
        await self._ensure_unique_identity(db, username=username, email=email, exclude_user_id=user.id)

        user.username = username
        user.display_name = payload["display_name"].strip()
        user.email = email
        user.phone = (payload.get("phone") or "").strip()

        await db.commit()
        await db.refresh(user)
        return self.serialize_user(user)

    async def change_password(self, db: AsyncSession, current_password: str, new_password: str, user_id: int) -> None:
        user = await self._get_user_by_id(db, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=404, detail="账户不存在或已停用")

        password_hash = user.password_hash or ""
        if password_hash and not _verify_password(current_password, password_hash):
            raise HTTPException(status_code=400, detail="当前密码错误")

        user.password_hash = _hash_password(new_password)
        await db.commit()

    async def authenticate(self, db: AsyncSession, login: str, password: str) -> dict[str, Any]:
        await self.ensure_bootstrap(db)
        user = await self._get_user_by_login(db, login)
        if user and not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号已停用，请联系超级管理员开通账号权限")
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

        if not user.password_hash:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="该账号尚未设置密码")

        if not _verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

        return self.serialize_user(user)

    async def request_registration_code(self, db: AsyncSession, email: str) -> dict[str, str]:
        from app.services.email import send_platform_email

        registration_status = await self.get_registration_status(db)
        if registration_status["bootstrap_mode"]:
            return {"message": "当前处于初始化模式，首个用户可直接注册，无需邮箱验证码"}

        normalized_email = email.strip().lower()
        if not normalized_email:
            raise HTTPException(status_code=400, detail="邮箱不能为空")

        existing_user = await self._get_user_by_email(db, normalized_email)
        if existing_user:
            raise HTTPException(status_code=400, detail="该邮箱已注册")

        key = _registration_key(normalized_email)
        result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        existing_code = result.scalar_one_or_none()
        now = datetime.utcnow()

        if existing_code and existing_code.config_value:
            try:
                metadata = json.loads(existing_code.config_value)
            except json.JSONDecodeError:
                metadata = {}
            sent_at = _parse_datetime(metadata.get("sent_at"))
            if sent_at and (now - sent_at).total_seconds() < REGISTRATION_CODE_COOLDOWN_SECONDS:
                raise HTTPException(status_code=429, detail="验证码发送过于频繁，请稍后再试")

        code = "".join(secrets.choice(string.digits) for _ in range(6))
        expires_at = now + timedelta(minutes=REGISTRATION_CODE_TTL_MINUTES)
        subject = "水浸监测系统注册验证码"
        message = (
            "您好，\n\n"
            f"您的水浸监测系统注册验证码为：{code}\n"
            f"验证码将在 {REGISTRATION_CODE_TTL_MINUTES} 分钟后失效。\n\n"
            "如果这不是您的操作，请忽略这封邮件。"
        )

        success, send_message = await send_platform_email(
            db,
            to=normalized_email,
            subject=subject,
            message=message,
        )
        if not success:
            raise HTTPException(status_code=500, detail=f"验证码发送失败：{send_message}")

        metadata = {
            "email": normalized_email,
            "code_hash": _hash_registration_code(normalized_email, code),
            "sent_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        await set_config_value(db, key, json.dumps(metadata, ensure_ascii=False), "注册验证码")
        await db.commit()

        return {"message": "验证码已发送，请检查邮箱"}

    async def register_user(self, db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        username = payload["username"].strip()
        display_name = (payload.get("display_name") or username).strip()
        email = payload["email"].strip().lower()
        password = str(payload["password"])
        verification_code = str(payload.get("verification_code") or "").strip()

        await self._ensure_unique_identity(db, username=username, email=email)

        has_usable_super_admin = await self._first_usable_super_admin_exists(db)
        code_config: SystemConfig | None = None
        if has_usable_super_admin:
            key = _registration_key(email)
            result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
            code_config = result.scalar_one_or_none()
            if not code_config or not code_config.config_value:
                raise HTTPException(status_code=400, detail="请先获取邮箱验证码")

            try:
                metadata = json.loads(code_config.config_value)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=400, detail="验证码已失效，请重新获取") from exc

            expires_at = _parse_datetime(metadata.get("expires_at"))
            if metadata.get("email") != email or not expires_at or expires_at < datetime.utcnow():
                raise HTTPException(status_code=400, detail="验证码已失效，请重新获取")

            expected_hash = metadata.get("code_hash")
            if expected_hash != _hash_registration_code(email, verification_code):
                raise HTTPException(status_code=400, detail="验证码错误")

        role = ROLE_SUPER_ADMIN if not has_usable_super_admin else ROLE_USER
        is_active = role == ROLE_SUPER_ADMIN
        user = AdminUser(
            username=username,
            display_name=display_name,
            email=email,
            phone="",
            role=role,
            password_hash=_hash_password(password),
            auth_provider="local",
            is_active=is_active,
        )
        db.add(user)
        await db.flush()

        if role == ROLE_SUPER_ADMIN:
            await self._disable_placeholder_bootstrap_admin(db)

        if code_config is not None:
            await db.delete(code_config)
        await db.commit()
        await db.refresh(user)
        return self.serialize_user(user)


account_service = AccountService()
