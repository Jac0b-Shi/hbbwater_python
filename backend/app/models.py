"""SQLAlchemy models for database tables."""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Boolean, 
    DECIMAL, DateTime, Date, Enum, JSON, ForeignKey, Index
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class SensorType(str, enum.Enum):
    ULTRASONIC = "ultrasonic"
    IMMERSION = "immersion"


class ReportMethod(str, enum.Enum):
    HTTP_API = "http_api"
    WEBHOOK = "webhook"
    MQTT = "mqtt"
    COAP = "coap"
    UDP_BINARY = "udp_binary"


class Status(str, enum.Enum):
    NORMAL = "normal"
    WARNING = "warning"
    DANGER = "danger"
    ALARM = "alarm"
    OFFLINE = "offline"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, enum.Enum):
    HIGH_WATER = "high_water"
    WATER_DETECTED = "water_detected"
    SENSOR_OFFLINE = "sensor_offline"
    LOW_BATTERY = "low_battery"


class Sensor(Base):
    __tablename__ = "sensors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sensor_id = Column(String(50), unique=True, nullable=False, index=True)
    sensor_type = Column(String(20), nullable=False)
    location = Column(String(100), nullable=False)
    description = Column(Text)
    warning_level = Column(DECIMAL(10, 2))
    danger_level = Column(DECIMAL(10, 2))
    normal_interval = Column(Integer, default=1800)
    alert_interval = Column(Integer, default=300)
    is_active = Column(Boolean, default=True)
    report_method = Column(String(20), default="http_api")
    webhook_token = Column(String(64), unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    readings = relationship("SensorReading", back_populates="sensor", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="sensor", cascade="all, delete-orphan")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sensor_id = Column(String(50), ForeignKey("sensors.sensor_id", ondelete="CASCADE"), nullable=False)
    sensor_type = Column(Enum(SensorType), nullable=False)
    # Ultrasonic fields
    water_level = Column(DECIMAL(10, 2))
    # Immersion fields
    water_detected = Column(Boolean)
    duration = Column(Integer)
    severity = Column(String(20))
    # Common fields
    status = Column(String(20), default="normal")
    battery_level = Column(DECIMAL(5, 2))
    signal_strength = Column(Integer)
    raw_data = Column(JSON)
    recorded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sensor = relationship("Sensor", back_populates="readings")
    
    __table_args__ = (
        Index("idx_sensor_time", "sensor_id", "recorded_at"),
        Index("idx_time", "recorded_at"),
        Index("idx_status", "status"),
    )


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sensor_id = Column(String(50), ForeignKey("sensors.sensor_id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(20), nullable=False)
    severity = Column(String(20), default="medium")
    message = Column(Text, nullable=False)
    details = Column(JSON)
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sensor = relationship("Sensor", back_populates="alerts")
    
    __table_args__ = (
        Index("idx_sensor", "sensor_id"),
        Index("idx_type", "alert_type"),
        Index("idx_severity", "severity"),
        Index("idx_created", "created_at"),
        Index("idx_resolved", "is_resolved"),
    )


class SystemConfig(Base):
    __tablename__ = "system_config"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False)
    config_value = Column(Text)
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
