"""Helpers for managing the switchable business database profiles."""
from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import (
    DatabaseSettings,
    activate_business_database,
    build_business_database_settings_from_env,
    get_business_runtime_state,
    get_current_business_settings,
    get_default_driver,
    should_auto_create_schema,
    test_business_database_settings,
)
from app.models import BusinessDbProfile


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return normalized


def _build_profile_key(display_name: str, dialect: str) -> str:
    slug = _slugify(display_name)
    if not slug:
        slug = f"{dialect}-{secrets.token_hex(4)}"
    return slug[:64]


def serialize_business_profile(profile: BusinessDbProfile) -> dict[str, Any]:
    """Return a client-safe representation of a stored business DB profile."""
    return {
        "id": profile.id,
        "profile_key": profile.profile_key,
        "display_name": profile.display_name,
        "dialect": profile.dialect,
        "driver": profile.driver,
        "host": profile.host or "",
        "port": profile.port or "",
        "service_name": profile.service_name or "",
        "database_name": profile.database_name,
        "username": profile.username,
        "password_set": bool(profile.password),
        "dm_home": profile.dm_home or "",
        "dm_svc_path": profile.dm_svc_path or "",
        "auto_create_schema": bool(profile.auto_create_schema),
        "is_active": bool(profile.is_active),
        "last_tested_at": profile.last_tested_at,
        "last_error": profile.last_error or "",
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def profile_to_settings(
    profile: BusinessDbProfile,
    *,
    password_override: str | None = None,
) -> DatabaseSettings:
    """Convert a stored control-plane profile into runtime DB settings."""
    password = profile.password
    if password_override is not None:
        password = password_override

    return DatabaseSettings(
        dialect=(profile.dialect or "").strip() or "mysql",
        driver=(profile.driver or "").strip() or get_default_driver(profile.dialect or "mysql"),
        host=(profile.host or "").strip(),
        port=(profile.port or "").strip(),
        database=(profile.database_name or "").strip(),
        username=(profile.username or "").strip(),
        password=password or "",
        service_name=(profile.service_name or "").strip(),
        dm_home=(profile.dm_home or "").strip(),
        dm_svc_path=(profile.dm_svc_path or "").strip(),
        auto_create_schema=profile.auto_create_schema,
    )


def payload_to_settings(payload: dict[str, Any], *, fallback_password: str = "") -> DatabaseSettings:
    """Convert an incoming admin payload into runtime DB settings."""
    dialect = (payload.get("dialect") or "").strip() or "mysql"
    driver = (payload.get("driver") or "").strip() or get_default_driver(dialect)
    password = payload.get("password")
    if password is None:
        password = fallback_password
    return DatabaseSettings(
        dialect=dialect,
        driver=driver,
        host=(payload.get("host") or "").strip(),
        port=str(payload.get("port") or "").strip(),
        database=(payload.get("database_name") or "").strip(),
        username=(payload.get("username") or "").strip(),
        password=password.strip() if isinstance(password, str) else "",
        service_name=(payload.get("service_name") or "").strip(),
        dm_home=(payload.get("dm_home") or "").strip(),
        dm_svc_path=(payload.get("dm_svc_path") or "").strip(),
        auto_create_schema=payload.get("auto_create_schema"),
    )


async def ensure_business_profiles_bootstrap(db: AsyncSession) -> list[BusinessDbProfile]:
    """Ensure the control DB always has at least one business profile."""
    result = await db.execute(select(BusinessDbProfile).order_by(BusinessDbProfile.created_at.asc()))
    profiles = list(result.scalars().all())
    if not profiles:
        settings = build_business_database_settings_from_env()
        display_name = "本地 MySQL" if settings.dialect == "mysql" else "环境默认业务库"
        profile = BusinessDbProfile(
            profile_key=_build_profile_key(display_name, settings.dialect),
            display_name=display_name,
            dialect=settings.dialect,
            driver=settings.driver or get_default_driver(settings.dialect),
            host=settings.host,
            port=settings.port,
            service_name=settings.service_name,
            database_name=settings.database,
            username=settings.username,
            password=settings.password,
            dm_home=settings.dm_home,
            dm_svc_path=settings.dm_svc_path,
            auto_create_schema=should_auto_create_schema(
                settings.dialect,
                configured=settings.auto_create_schema,
            ),
            is_active=True,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return [profile]

    active_profiles = [profile for profile in profiles if profile.is_active]
    if not active_profiles:
        profiles[0].is_active = True
        await db.commit()
    elif len(active_profiles) > 1:
        keep_id = active_profiles[0].id
        for profile in profiles:
            profile.is_active = profile.id == keep_id
        await db.commit()

    result = await db.execute(select(BusinessDbProfile).order_by(BusinessDbProfile.created_at.asc()))
    return list(result.scalars().all())


async def get_business_profiles_state(db: AsyncSession) -> dict[str, Any]:
    """Return the admin-facing business DB profile catalog and runtime state."""
    profiles = await ensure_business_profiles_bootstrap(db)
    active_profile = next((profile for profile in profiles if profile.is_active), None)
    runtime = get_business_runtime_state()
    current_settings = get_current_business_settings()
    return {
        "active_profile_id": active_profile.id if active_profile else None,
        "runtime": {
            **runtime,
            "display_name": active_profile.display_name if active_profile else "未配置",
            "database": current_settings.database,
            "host": current_settings.host,
            "service_name": current_settings.service_name,
        },
        "profiles": [serialize_business_profile(profile) for profile in profiles],
    }


async def save_business_profile(db: AsyncSession, payload: dict[str, Any]) -> BusinessDbProfile:
    """Create or update a stored business database profile."""
    profiles = await ensure_business_profiles_bootstrap(db)
    profile_id = payload.get("id")
    profile = next((item for item in profiles if item.id == profile_id), None) if profile_id else None
    if profile_id and profile is None:
        raise ValueError("数据库配置不存在")

    display_name = (payload.get("display_name") or "").strip()
    if not display_name:
        raise ValueError("请填写配置名称")

    dialect = (payload.get("dialect") or "").strip() or (profile.dialect if profile else "mysql")
    driver = (payload.get("driver") or "").strip() or get_default_driver(dialect)
    profile_key = (payload.get("profile_key") or "").strip()
    if not profile_key:
        profile_key = profile.profile_key if profile else _build_profile_key(display_name, dialect)

    duplicate = await db.execute(
        select(BusinessDbProfile).where(
            BusinessDbProfile.profile_key == profile_key,
            BusinessDbProfile.id != (profile.id if profile else 0),
        )
    )
    if duplicate.scalar_one_or_none():
        raise ValueError("配置标识已存在，请更换名称")

    password = payload.get("password")
    if password is None:
        password = profile.password if profile else ""
    else:
        password = password.strip()
    if payload.get("clear_password"):
        password = ""

    target = profile or BusinessDbProfile(
        profile_key=profile_key,
        display_name=display_name,
        dialect=dialect,
        driver=driver,
        database_name="",
        username="",
    )
    target.profile_key = profile_key
    target.display_name = display_name
    target.dialect = dialect
    target.driver = driver
    target.host = (payload.get("host") or "").strip()
    target.port = str(payload.get("port") or "").strip()
    target.service_name = (payload.get("service_name") or "").strip()
    target.database_name = (payload.get("database_name") or "").strip()
    target.username = (payload.get("username") or "").strip()
    target.password = password
    target.dm_home = (payload.get("dm_home") or "").strip()
    target.dm_svc_path = (payload.get("dm_svc_path") or "").strip()
    target.auto_create_schema = bool(payload.get("auto_create_schema"))
    target.updated_at = datetime.utcnow()
    if profile is None:
        db.add(target)
    await db.commit()
    await db.refresh(target)
    return target


async def test_business_profile_payload(db: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a profile payload without changing the active runtime."""
    existing_password = ""
    profile_id = payload.get("id")
    if profile_id:
        result = await db.execute(select(BusinessDbProfile).where(BusinessDbProfile.id == profile_id))
        existing = result.scalar_one_or_none()
        if existing:
            existing_password = existing.password or ""

    settings = payload_to_settings(payload, fallback_password=existing_password)
    result = await test_business_database_settings(settings)

    if profile_id:
        result_query = await db.execute(select(BusinessDbProfile).where(BusinessDbProfile.id == profile_id))
        profile = result_query.scalar_one_or_none()
        if profile:
            profile.last_tested_at = datetime.utcnow()
            profile.last_error = ""
            await db.commit()

    return result


async def activate_business_profile(db: AsyncSession, profile_id: int) -> BusinessDbProfile:
    """Activate a stored business DB profile and hot-swap the runtime sessionmaker."""
    await ensure_business_profiles_bootstrap(db)
    result = await db.execute(select(BusinessDbProfile).where(BusinessDbProfile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise ValueError("数据库配置不存在")

    try:
        await activate_business_database(profile_to_settings(profile))
    except Exception as exc:
        profile.last_tested_at = datetime.utcnow()
        profile.last_error = str(exc)
        await db.commit()
        raise

    await db.execute(update(BusinessDbProfile).values(is_active=False))
    profile.is_active = True
    profile.last_tested_at = datetime.utcnow()
    profile.last_error = ""
    await db.commit()
    await db.refresh(profile)
    return profile
