"""Pure Python MQTT/HTTP payload parsing."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ParsedPayload:
    device_id: str
    sensor_type: str
    value: float
    unit: str
    battery: int | None
    rssi: int | None
    timestamp: datetime | None
    raw: dict[str, Any]


def parse_topic(topic: str | None) -> tuple[str | None, str | None]:
    if not topic:
        return None, None
    parts = topic.split("/")
    if len(parts) >= 4 and parts[0] == "hbbwater":
        return parts[1], parts[2]
    return None, None


def normalize_unit(value: float, unit: str | None) -> tuple[float, str]:
    normalized_unit = (unit or "cm").lower()
    if normalized_unit == "mm":
        return value / 10.0, "cm"
    if normalized_unit in {"centimeter", "centimeters"}:
        return value, "cm"
    if normalized_unit in {"bool", "boolean"}:
        return value, "state"
    return value, normalized_unit


def parse_sensor_payload(payload: dict[str, Any], topic: str | None = None) -> ParsedPayload:
    topic_type, topic_device = parse_topic(topic)
    device_id = str(payload.get("device_id") or payload.get("deviceId") or payload.get("sensor_id") or topic_device or "")
    sensor_type = str(payload.get("type") or payload.get("sensor_type") or topic_type or "")

    if not device_id:
        raise ValueError("device_id is required")
    if sensor_type not in {"ultrasonic", "immersion"}:
        raise ValueError("sensor type must be ultrasonic or immersion")

    if sensor_type == "immersion":
        if "water_detected" in payload:
            value = 1.0 if bool(payload["water_detected"]) else 0.0
            unit = "state"
        else:
            value = 1.0 if bool(payload.get("value")) else 0.0
            unit = "state"
    else:
        raw_value = payload.get("value", payload.get("water_level"))
        if raw_value is None:
            raise ValueError("value or water_level is required for ultrasonic sensor")
        value = float(raw_value)
        value, unit = normalize_unit(value, str(payload.get("unit", "cm")))

    timestamp = payload.get("timestamp") or payload.get("created_at")
    parsed_time = None
    if isinstance(timestamp, datetime):
        parsed_time = timestamp
    elif isinstance(timestamp, str) and timestamp:
        parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    battery = payload.get("battery", payload.get("battery_level"))
    rssi = payload.get("rssi", payload.get("signal_strength"))
    return ParsedPayload(
        device_id=device_id,
        sensor_type=sensor_type,
        value=float(value),
        unit=unit,
        battery=int(battery) if battery is not None else None,
        rssi=int(rssi) if rssi is not None else None,
        timestamp=parsed_time,
        raw=dict(payload),
    )

