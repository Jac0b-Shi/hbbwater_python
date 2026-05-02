"""Default users, sensors, and system settings for course demos."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Sensor, SystemConfig, User
from app.services.auth import hash_password


DEFAULT_CONFIGS = {
    "data_retention_days": {"value": 14},
    "offline_timeout_seconds": {"value": 300},
    "alert_cooldown_minutes": {"value": 30},
    "notification": {"webhook_enabled": False, "email_enabled": False},
}


async def seed_defaults(session: AsyncSession) -> None:
    user_exists = await session.scalar(select(User.id).limit(1))
    if not user_exists:
        session.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
                display_name="系统管理员",
                email=settings.admin_email,
                role="super_admin",
            )
        )

    sensor_exists = await session.scalar(select(Sensor.id).limit(1))
    if not sensor_exists:
        session.add_all(
            [
                Sensor(
                    device_id="US001",
                    name="一号楼地下室超声波水位",
                    type="ultrasonic",
                    location="一号楼地下室排水沟",
                    map_x=32.0,
                    map_y=58.0,
                    threshold_warn=10.0,
                    threshold_danger=20.0,
                ),
                Sensor(
                    device_id="IM001",
                    name="实验楼弱电井浸水",
                    type="immersion",
                    location="实验楼弱电井",
                    map_x=68.0,
                    map_y=42.0,
                    threshold_warn=1.0,
                    threshold_danger=1.0,
                ),
            ]
        )

    for key, value in DEFAULT_CONFIGS.items():
        exists = await session.scalar(select(SystemConfig).where(SystemConfig.key == key))
        if not exists:
            session.add(SystemConfig(key=key, value=value))

    await session.commit()

