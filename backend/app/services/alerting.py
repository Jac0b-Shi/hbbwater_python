"""Alert engine with cooldown and auto resolution."""

from datetime import timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Alert, Sensor, SensorReading, utcnow
from app.services.status import evaluate_status


async def resolve_sensor_alerts(session: AsyncSession, sensor: Sensor) -> None:
    result = await session.scalars(
        select(Alert).where(Alert.sensor_id == sensor.id, Alert.status == "active")
    )
    now = utcnow()
    for alert in result:
        alert.status = "resolved"
        alert.resolved_at = now


async def evaluate_reading(session: AsyncSession, sensor: Sensor, reading: SensorReading) -> Alert | None:
    decision = evaluate_status(
        sensor_type=sensor.type,
        device_id=sensor.device_id,
        value=reading.value,
        unit=reading.unit,
        threshold_warn=sensor.threshold_warn,
        threshold_danger=sensor.threshold_danger,
        threshold_dir=sensor.threshold_dir,
    )
    reading.status = decision.status

    if decision.status == "normal":
        await resolve_sensor_alerts(session, sensor)
        return None

    assert decision.alert_type and decision.severity and decision.message
    now = utcnow()
    active_alert = await session.scalar(
        select(Alert)
        .where(
            Alert.sensor_id == sensor.id,
            Alert.type == decision.alert_type,
            Alert.status == "active",
        )
        .order_by(desc(Alert.triggered_at))
    )
    if active_alert:
        active_alert.severity = decision.severity
        active_alert.message = decision.message
        active_alert.cooldown_until = now + timedelta(minutes=settings.alert_cooldown_minutes)
        return None

    recent_alert = await session.scalar(
        select(Alert)
        .where(Alert.sensor_id == sensor.id, Alert.type == decision.alert_type)
        .order_by(desc(Alert.triggered_at))
    )
    if recent_alert and recent_alert.cooldown_until and recent_alert.cooldown_until > now:
        return None

    alert = Alert(
        sensor_id=sensor.id,
        type=decision.alert_type,
        severity=decision.severity,
        message=decision.message,
        status="active",
        triggered_at=now,
        cooldown_until=now + timedelta(minutes=settings.alert_cooldown_minutes),
    )
    session.add(alert)
    await session.flush()
    return alert

