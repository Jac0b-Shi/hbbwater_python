"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator


# ==================== Sensor Schemas ====================

class SensorBase(BaseModel):
    sensor_id: str = Field(..., max_length=50)
    sensor_type: str = Field(..., pattern="^(ultrasonic|immersion)$")
    location: str = Field(..., max_length=100)
    description: Optional[str] = None
    warning_level: Optional[Decimal] = None
    danger_level: Optional[Decimal] = None
    normal_interval: int = Field(default=1800, ge=60)
    alert_interval: int = Field(default=300, ge=60)
    is_active: bool = True
    report_method: str = Field(default="http_api", pattern="^(http_api|webhook|mqtt|coap|udp_binary)$")
    webhook_token: Optional[str] = Field(None, max_length=64)


class SensorCreate(SensorBase):
    pass


class SensorUpdate(BaseModel):
    sensor_type: Optional[str] = Field(None, pattern="^(ultrasonic|immersion)$")
    location: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    warning_level: Optional[Decimal] = None
    danger_level: Optional[Decimal] = None
    normal_interval: Optional[int] = Field(None, ge=60)
    alert_interval: Optional[int] = Field(None, ge=60)
    is_active: Optional[bool] = None
    report_method: Optional[str] = Field(None, pattern="^(http_api|webhook|mqtt|coap|udp_binary)$")
    webhook_token: Optional[str] = Field(None, max_length=64)


class SensorResponse(SensorBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Sensor Reading Schemas ====================

class UltrasonicReading(BaseModel):
    water_level: Decimal = Field(..., description="水位(cm)")
    battery_level: Optional[Decimal] = Field(None, ge=0, le=100)
    signal_strength: Optional[int] = None


class ImmersionReading(BaseModel):
    water_detected: bool
    duration: Optional[int] = Field(None, ge=0, description="持续时间(秒)")
    severity: Optional[str] = Field(None, pattern="^(low|medium|high)$")


class SensorDataInput(BaseModel):
    sensor_id: str
    sensor_type: str = Field(..., pattern="^(ultrasonic|immersion)$")
    timestamp: Optional[datetime] = None
    status: str = Field(default="normal", pattern="^(normal|warning|danger|alarm|offline)$")
    location: Optional[str] = None
    # Ultrasonic fields
    water_level: Optional[Decimal] = None
    battery_level: Optional[Decimal] = Field(None, ge=0, le=100)
    signal_strength: Optional[int] = None
    # Immersion fields
    water_detected: Optional[bool] = None
    duration: Optional[int] = None
    severity: Optional[str] = None
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            # Handle ISO format with Z
            if v.endswith('Z'):
                v = v[:-1] + '+00:00'
            return datetime.fromisoformat(v)
        return v


class WebhookDataInput(BaseModel):
    """JSON payload received via sensor webhook."""
    timestamp: Optional[datetime] = None
    status: str = Field(default="normal", pattern="^(normal|warning|danger|alarm|offline)$")
    # Ultrasonic fields
    water_level: Optional[Decimal] = None
    battery_level: Optional[Decimal] = Field(None, ge=0, le=100)
    signal_strength: Optional[int] = None
    # Immersion fields
    water_detected: Optional[bool] = None
    duration: Optional[int] = None
    severity: Optional[str] = None
    
    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            if v.endswith('Z'):
                v = v[:-1] + '+00:00'
            return datetime.fromisoformat(v)
        return v


class SensorReadingResponse(BaseModel):
    id: int
    sensor_id: str
    sensor_type: str
    water_level: Optional[Decimal]
    water_detected: Optional[bool]
    duration: Optional[int]
    severity: Optional[str]
    status: str
    battery_level: Optional[Decimal]
    signal_strength: Optional[int]
    recorded_at: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True


class SensorReadingList(BaseModel):
    items: List[SensorReadingResponse]
    total: int
    page: int
    page_size: int


# ==================== Alert Schemas ====================

class AlertCreate(BaseModel):
    sensor_id: str
    alert_type: str = Field(..., pattern="^(high_water|water_detected|sensor_offline|low_battery)$")
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    message: str
    details: Optional[Dict[str, Any]] = None


class AlertResponse(BaseModel):
    id: int
    sensor_id: str
    alert_type: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]]
    is_resolved: bool
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AlertResolveRequest(BaseModel):
    resolved_by: str = Field(..., max_length=50)


# ==================== Dashboard Schemas ====================

class SensorStatus(BaseModel):
    sensor_id: str
    sensor_type: str
    location: str
    status: str
    last_reading: Optional[datetime]
    battery_level: Optional[Decimal]
    water_level: Optional[Decimal]
    water_detected: Optional[bool]
    is_online: bool


class DashboardStats(BaseModel):
    total_sensors: int
    online_sensors: int
    offline_sensors: int
    active_alerts: int
    today_readings: int
    ultrasonic_sensors: int
    immersion_sensors: int


class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    value: Union[Decimal, int, bool, None]


class SensorTimeSeries(BaseModel):
    sensor_id: str
    sensor_type: str
    location: str
    data: List[TimeSeriesPoint]


# ==================== System Config Schemas ====================

class SystemConfigResponse(BaseModel):
    config_key: str
    config_value: str
    description: Optional[str]
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Generic Response ====================

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None


class HealthCheck(BaseModel):
    status: str
    version: str
    database: str
    timestamp: datetime
