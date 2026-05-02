"""Sensor ingestion service shared by HTTP and MQTT entry points."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Sensor, SensorReading, utcnow
from app.schemas import ReadingIn
from app.services.alerting import evaluate_reading
from app.services.notifications import send_alert_notification
from app.services.payload import parse_sensor_payload


def default_thresholds(sensor_type: str) -> tuple[float | None, float | None, str]:
    if sensor_type == "immersion":
        return 1.0, 1.0, "greater_or_equal"
    return 10.0, 20.0, "greater_or_equal"


async def get_or_create_sensor(session: AsyncSession, device_id: str, sensor_type: str) -> Sensor:
    sensor = await session.scalar(select(Sensor).where(Sensor.device_id == device_id))
    if sensor:
        return sensor

    warn, danger, direction = default_thresholds(sensor_type)
    sensor = Sensor(
        device_id=device_id,
        name=device_id,
        type=sensor_type,
        location="未配置位置",
        map_x=50.0,
        map_y=50.0,
        threshold_warn=warn,
        threshold_danger=danger,
        threshold_dir=direction,
    )
    session.add(sensor)
    await session.flush()
    return sensor


async def ingest_payload(session: AsyncSession, payload: dict, topic: str | None = None) -> tuple[SensorReading, Alert | None]:
    parsed = parse_sensor_payload(payload, topic)
    sensor = await get_or_create_sensor(session, parsed.device_id, parsed.sensor_type)
    recorded_at = parsed.timestamp or utcnow()
    sensor.last_value = parsed.value
    sensor.last_unit = parsed.unit
    sensor.last_seen_at = recorded_at

    reading = SensorReading(
        sensor_id=sensor.id,
        value=parsed.value,
        unit=parsed.unit,
        battery=parsed.battery,
        rssi=parsed.rssi,
        raw_json=parsed.raw,
        created_at=recorded_at,
    )
    session.add(reading)
    await session.flush()
    alert = await evaluate_reading(session, sensor, reading)
    await session.commit()

    if alert:
        try:
            await send_alert_notification(alert, sensor)
        except Exception:
            pass

    return reading, alert


async def ingest_reading_model(session: AsyncSession, data: ReadingIn, topic: str | None = None) -> tuple[SensorReading, Alert | None]:
    payload = data.model_dump(exclude_none=True)
    if data.raw:
        payload.update(data.raw)
    return await ingest_payload(session, payload, topic)

