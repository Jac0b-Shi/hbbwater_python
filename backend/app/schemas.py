"""Pydantic request and response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    email: str = ""
    phone: str = ""


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    email: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime


class SensorBase(BaseModel):
    device_id: str
    name: str = ""
    type: str = Field(pattern="^(ultrasonic|immersion)$")
    location: str = ""
    map_x: float | None = Field(default=None, ge=0, le=100)
    map_y: float | None = Field(default=None, ge=0, le=100)
    map_locked: bool = False
    water_level_baseline: float | None = None
    threshold_warn: float | None = None
    threshold_danger: float | None = None
    threshold_dir: str = Field(default="greater_or_equal", pattern="^(greater_or_equal|less_or_equal)$")
    report_interval: int = 60
    alert_interval: int = 10
    is_active: bool = True


class SensorCreate(SensorBase):
    pass


class SensorUpdate(BaseModel):
    name: str | None = None
    type: str | None = Field(default=None, pattern="^(ultrasonic|immersion)$")
    location: str | None = None
    map_x: float | None = Field(default=None, ge=0, le=100)
    map_y: float | None = Field(default=None, ge=0, le=100)
    map_locked: bool | None = None
    water_level_baseline: float | None = None
    threshold_warn: float | None = None
    threshold_danger: float | None = None
    threshold_dir: str | None = Field(default=None, pattern="^(greater_or_equal|less_or_equal)$")
    report_interval: int | None = None
    alert_interval: int | None = None
    is_active: bool | None = None


class SensorOut(SensorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_value: float | None
    last_unit: str
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReadingIn(BaseModel):
    device_id: str | None = None
    timestamp: datetime | None = None
    type: str | None = Field(default=None, pattern="^(ultrasonic|immersion)$")
    value: float | bool | int | None = None
    water_level: float | None = None
    water_detected: bool | None = None
    unit: str = "cm"
    battery: int | None = Field(default=None, ge=0, le=100)
    rssi: int | None = None
    raw: dict[str, Any] | None = None


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: int
    value: float
    unit: str
    battery: int | None
    rssi: int | None
    status: str
    raw_json: dict[str, Any]
    created_at: datetime


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: int
    type: str
    severity: str
    message: str
    status: str
    triggered_at: datetime
    resolved_at: datetime | None
    cooldown_until: datetime | None


class DashboardStats(BaseModel):
    sensors_total: int
    sensors_online: int
    active_alerts: int
    readings_today: int


class ConfigOut(BaseModel):
    key: str
    value: dict[str, Any]
    updated_at: datetime


class ConfigUpdate(BaseModel):
    key: str
    value: dict[str, Any]
