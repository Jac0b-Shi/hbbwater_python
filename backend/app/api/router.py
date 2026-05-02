"""FastAPI endpoints for the course project."""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.config import settings
from app.database import get_session
from app.models import Alert, Sensor, SensorReading, SystemConfig, User
from app.schemas import (
    AlertOut,
    ConfigOut,
    ConfigUpdate,
    DashboardStats,
    ReadingIn,
    ReadingOut,
    SensorCreate,
    SensorOut,
    SensorUpdate,
    TokenRequest,
    TokenResponse,
    UserCreate,
    UserOut,
)
from app.services.auth import create_access_token, hash_password, verify_password
from app.services.ingestion import ingest_payload, ingest_reading_model

router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(data: TokenRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    user = await session.scalar(select(User).where(User.username == data.username))
    if not user or not verify_password(data.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(access_token=token)


@router.post("/auth/register", response_model=UserOut, tags=["auth"])
async def register(data: UserCreate, session: AsyncSession = Depends(get_session)) -> User:
    existing = await session.scalar(select(User).where(User.username == data.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    first_user = await session.scalar(select(User.id).limit(1))
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name or data.username,
        email=data.email,
        phone=data.phone,
        role="super_admin" if not first_user else "user",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/account/me", response_model=UserOut, tags=["account"])
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/account/users", response_model=list[UserOut], tags=["account"])
async def list_users(
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    result = await session.scalars(select(User).order_by(User.id))
    return list(result)


@router.get("/sensors", response_model=list[SensorOut], tags=["sensors"])
async def list_sensors(
    sensor_type: str | None = Query(default=None, alias="type"),
    session: AsyncSession = Depends(get_session),
) -> list[Sensor]:
    query = select(Sensor).order_by(Sensor.device_id)
    if sensor_type:
        query = query.where(Sensor.type == sensor_type)
    result = await session.scalars(query)
    return list(result)


@router.post("/sensors", response_model=SensorOut, tags=["sensors"])
async def create_sensor(data: SensorCreate, session: AsyncSession = Depends(get_session)) -> Sensor:
    existing = await session.scalar(select(Sensor).where(Sensor.device_id == data.device_id))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sensor already exists")
    sensor = Sensor(**data.model_dump())
    session.add(sensor)
    await session.commit()
    await session.refresh(sensor)
    return sensor


@router.get("/sensors/{sensor_id}", response_model=SensorOut, tags=["sensors"])
async def get_sensor(sensor_id: int, session: AsyncSession = Depends(get_session)) -> Sensor:
    sensor = await session.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    return sensor


@router.put("/sensors/{sensor_id}", response_model=SensorOut, tags=["sensors"])
async def update_sensor(sensor_id: int, data: SensorUpdate, session: AsyncSession = Depends(get_session)) -> Sensor:
    sensor = await session.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(sensor, field, value)
    await session.commit()
    await session.refresh(sensor)
    return sensor


@router.delete("/sensors/{sensor_id}", tags=["sensors"])
async def delete_sensor(sensor_id: int, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    sensor = await session.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")
    await session.delete(sensor)
    await session.commit()
    return {"status": "deleted"}


@router.get("/sensors/{sensor_id}/readings", response_model=list[ReadingOut], tags=["readings"])
async def sensor_readings(
    sensor_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[SensorReading]:
    result = await session.scalars(
        select(SensorReading)
        .where(SensorReading.sensor_id == sensor_id)
        .order_by(desc(SensorReading.created_at))
        .limit(limit)
    )
    return list(result)


@router.post("/sensors/{device_id}/readings", response_model=ReadingOut, tags=["readings"])
async def create_device_reading(
    device_id: str,
    data: ReadingIn,
    session: AsyncSession = Depends(get_session),
) -> SensorReading:
    payload = data.model_dump(exclude_none=True)
    payload["device_id"] = device_id
    reading, _ = await ingest_payload(session, payload)
    return reading


@router.post("/ingest/http", response_model=ReadingOut, tags=["ingress"])
async def http_ingest(data: ReadingIn, session: AsyncSession = Depends(get_session)) -> SensorReading:
    reading, _ = await ingest_reading_model(session, data)
    return reading


@router.get("/readings/recent", response_model=list[ReadingOut], tags=["readings"])
async def recent_readings(
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[SensorReading]:
    result = await session.scalars(select(SensorReading).order_by(desc(SensorReading.created_at)).limit(limit))
    return list(result)


@router.get("/alerts", response_model=list[AlertOut], tags=["alerts"])
async def list_alerts(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[Alert]:
    query = select(Alert).order_by(desc(Alert.triggered_at)).limit(limit)
    if status_filter:
        query = query.where(Alert.status == status_filter)
    result = await session.scalars(query)
    return list(result)


@router.put("/alerts/{alert_id}/resolve", response_model=AlertOut, tags=["alerts"])
async def resolve_alert(alert_id: int, session: AsyncSession = Depends(get_session)) -> Alert:
    alert = await session.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(alert)
    return alert


@router.get("/alerts/stats", tags=["alerts"])
async def alert_stats(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    active = await session.scalar(select(func.count()).select_from(Alert).where(Alert.status == "active"))
    total = await session.scalar(select(func.count()).select_from(Alert))
    by_severity = {}
    rows = await session.execute(select(Alert.severity, func.count()).group_by(Alert.severity))
    for severity, count in rows:
        by_severity[severity] = count
    return {"total": total or 0, "active": active or 0, "by_severity": by_severity}


@router.get("/dashboard/stats", response_model=DashboardStats, tags=["dashboard"])
async def dashboard_stats(session: AsyncSession = Depends(get_session)) -> DashboardStats:
    now = datetime.now(timezone.utc)
    online_after = now - timedelta(seconds=settings.offline_timeout_seconds)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sensors_total = await session.scalar(select(func.count()).select_from(Sensor))
    sensors_online = await session.scalar(
        select(func.count()).select_from(Sensor).where(Sensor.last_seen_at >= online_after)
    )
    active_alerts = await session.scalar(select(func.count()).select_from(Alert).where(Alert.status == "active"))
    readings_today = await session.scalar(
        select(func.count()).select_from(SensorReading).where(SensorReading.created_at >= today)
    )
    return DashboardStats(
        sensors_total=sensors_total or 0,
        sensors_online=sensors_online or 0,
        active_alerts=active_alerts or 0,
        readings_today=readings_today or 0,
    )


@router.get("/dashboard/sensor-status", tags=["dashboard"])
async def sensor_status(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    online_after = now - timedelta(seconds=settings.offline_timeout_seconds)
    sensors = await session.scalars(select(Sensor).order_by(Sensor.device_id))
    data = []
    for sensor in sensors:
        latest_reading = await session.scalar(
            select(SensorReading).where(SensorReading.sensor_id == sensor.id).order_by(desc(SensorReading.created_at)).limit(1)
        )
        data.append(
            {
                "id": sensor.id,
                "device_id": sensor.device_id,
                "name": sensor.name,
                "type": sensor.type,
                "location": sensor.location,
                "is_active": sensor.is_active,
                "last_value": sensor.last_value,
                "last_unit": sensor.last_unit,
                "last_status": latest_reading.status if latest_reading else "offline",
                "last_battery": latest_reading.battery if latest_reading else None,
                "last_rssi": latest_reading.rssi if latest_reading else None,
                "last_seen_at": sensor.last_seen_at,
                "online": bool(sensor.last_seen_at and sensor.last_seen_at >= online_after),
                "map_x": sensor.map_x,
                "map_y": sensor.map_y,
                "map_locked": sensor.map_locked,
                "water_level_baseline": sensor.water_level_baseline,
            }
        )
    return data


@router.get("/config", response_model=list[ConfigOut], tags=["config"])
async def list_config(session: AsyncSession = Depends(get_session)) -> list[SystemConfig]:
    result = await session.scalars(select(SystemConfig).order_by(SystemConfig.key))
    return list(result)


@router.put("/config", response_model=ConfigOut, tags=["config"])
async def upsert_config(data: ConfigUpdate, session: AsyncSession = Depends(get_session)) -> SystemConfig:
    config = await session.get(SystemConfig, data.key)
    if config:
        config.value = data.value
    else:
        config = SystemConfig(key=data.key, value=data.value)
        session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.post("/config/maintenance", tags=["config"])
async def maintenance(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    old_count = await session.scalar(select(func.count()).select_from(SensorReading).where(SensorReading.created_at < cutoff))
    return {"status": "checked", "archive_candidate_readings": old_count or 0}
