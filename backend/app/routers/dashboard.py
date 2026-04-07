"""Dashboard and statistics API routes."""
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Sensor, SensorReading, Alert, SensorType
from app.schemas import DashboardStats, SensorStatus
from app.services.system_config import get_offline_timeout_minutes
from app.services.text import repair_mojibake

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    # Total sensors
    total_result = await db.execute(select(func.count()).select_from(Sensor))
    total_sensors = total_result.scalar()
    
    # Sensor types count
    type_query = select(
        Sensor.sensor_type,
        func.count().label("count")
    ).where(Sensor.is_active == True).group_by(Sensor.sensor_type)
    
    type_result = await db.execute(type_query)
    type_counts = {row[0]: row[1] for row in type_result.all()}
    
    # Active alerts
    alerts_result = await db.execute(
        select(func.count()).where(Alert.is_resolved == False)
    )
    active_alerts = alerts_result.scalar()
    
    # Today's readings
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    readings_result = await db.execute(
        select(func.count()).where(SensorReading.recorded_at >= today)
    )
    today_readings = readings_result.scalar()
    
    # Online/offline calculation
    offline_timeout_minutes = await get_offline_timeout_minutes(db)
    offline_threshold = datetime.utcnow() - timedelta(minutes=offline_timeout_minutes)
    
    # Get latest reading time for each sensor
    latest_readings_query = select(
        SensorReading.sensor_id,
        func.max(SensorReading.recorded_at).label("last_reading")
    ).group_by(SensorReading.sensor_id)
    
    latest_result = await db.execute(latest_readings_query)
    latest_times = {row[0]: row[1] for row in latest_result.all()}
    
    # Count online sensors
    online_count = sum(
        1 for last_time in latest_times.values()
        if last_time and last_time > offline_threshold
    )
    
    return DashboardStats(
        total_sensors=total_sensors,
        online_sensors=online_count,
        offline_sensors=total_sensors - online_count,
        active_alerts=active_alerts,
        today_readings=today_readings,
        ultrasonic_sensors=type_counts.get("ultrasonic", 0),
        immersion_sensors=type_counts.get("immersion", 0)
    )


@router.get("/sensor-status", response_model=List[SensorStatus])
async def get_all_sensors_status(db: AsyncSession = Depends(get_db)):
    """Get current status of all sensors."""
    query = select(Sensor).where(Sensor.is_active == True)
    result = await db.execute(query)
    sensors = result.scalars().all()
    
    offline_timeout_minutes = await get_offline_timeout_minutes(db)
    offline_threshold = datetime.utcnow() - timedelta(minutes=offline_timeout_minutes)
    statuses = []
    
    for sensor in sensors:
        # Get latest reading
        reading_query = select(SensorReading).where(
            SensorReading.sensor_id == sensor.sensor_id
        ).order_by(desc(SensorReading.recorded_at)).limit(1)
        
        reading_result = await db.execute(reading_query)
        latest_reading = reading_result.scalar_one_or_none()
        
        is_online = (
            latest_reading is not None and 
            latest_reading.recorded_at > offline_threshold
        )
        
        statuses.append(SensorStatus(
            sensor_id=sensor.sensor_id,
            sensor_type=sensor.sensor_type,
            location=sensor.location,
            status=latest_reading.status if latest_reading else "offline",
            last_reading=latest_reading.recorded_at if latest_reading else None,
            battery_level=latest_reading.battery_level if latest_reading else None,
            external_powered=latest_reading.external_powered if latest_reading else False,
            water_level=latest_reading.water_level if latest_reading else None,
            water_detected=latest_reading.water_detected if latest_reading else None,
            is_online=is_online
        ))
    
    return statuses


@router.get("/recent-readings")
async def get_recent_readings(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get recent sensor readings across all sensors."""
    query = select(
        SensorReading,
        Sensor.location,
        Sensor.sensor_type
    ).join(
        Sensor, SensorReading.sensor_id == Sensor.sensor_id
    ).order_by(
        desc(SensorReading.recorded_at)
    ).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    readings = []
    for row in rows:
        reading = row[0]
        readings.append({
            "id": reading.id,
            "sensor_id": reading.sensor_id,
            "sensor_type": row[2],
            "location": row[1],
            "water_level": float(reading.water_level) if reading.water_level else None,
            "water_detected": reading.water_detected,
            "status": reading.status,
            "battery_level": float(reading.battery_level) if reading.battery_level else None,
            "external_powered": reading.external_powered,
            "recorded_at": reading.recorded_at.isoformat()
        })
    
    return readings


@router.get("/alerts/recent")
async def get_recent_alerts(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Get recent active alerts."""
    query = select(
        Alert,
        Sensor.location
    ).join(
        Sensor, Alert.sensor_id == Sensor.sensor_id
    ).where(
        Alert.is_resolved == False
    ).order_by(
        desc(Alert.created_at)
    ).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    alerts = []
    for row in rows:
        alert = row[0]
        alerts.append({
            "id": alert.id,
            "sensor_id": alert.sensor_id,
            "location": row[1],
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "message": repair_mojibake(alert.message) or "",
            "created_at": alert.created_at.isoformat()
        })
    
    return alerts
