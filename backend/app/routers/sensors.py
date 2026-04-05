"""Sensor data API routes."""
from datetime import datetime, timedelta
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Sensor, SensorReading, SensorType, Status
from app.schemas import (
    SensorCreate, SensorUpdate, SensorResponse,
    SensorDataInput, SensorReadingResponse, SensorReadingList,
    SensorStatus, SensorTimeSeries, TimeSeriesPoint,
    WebhookDataInput
)
import uuid

router = APIRouter(prefix="/sensors", tags=["sensors"])


@router.get("/", response_model=List[SensorResponse])
async def list_sensors(
    sensor_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all sensors with optional filtering."""
    query = select(Sensor)
    
    if sensor_type:
        query = query.where(Sensor.sensor_type == sensor_type)
    if is_active is not None:
        query = query.where(Sensor.is_active == is_active)
    
    result = await db.execute(query.order_by(Sensor.created_at.desc()))
    return result.scalars().all()


@router.get("/{sensor_id}", response_model=SensorResponse)
async def get_sensor(sensor_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific sensor by ID."""
    result = await db.execute(select(Sensor).where(Sensor.sensor_id == sensor_id))
    sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return sensor


@router.post("/", response_model=SensorResponse, status_code=201)
async def create_sensor(sensor: SensorCreate, db: AsyncSession = Depends(get_db)):
    """Create a new sensor."""
    # Check if sensor_id already exists
    result = await db.execute(select(Sensor).where(Sensor.sensor_id == sensor.sensor_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Sensor ID already exists")
    
    sensor_data = sensor.model_dump()
    # Auto-generate webhook token for webhook-enabled sensors
    if sensor_data.get("report_method") in ("webhook", "mqtt", "coap"):
        sensor_data["webhook_token"] = uuid.uuid4().hex[:16]
    
    db_sensor = Sensor(**sensor_data)
    db.add(db_sensor)
    await db.commit()
    await db.refresh(db_sensor)
    return db_sensor


@router.patch("/{sensor_id}", response_model=SensorResponse)
async def update_sensor(
    sensor_id: str, 
    sensor_update: SensorUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update a sensor configuration."""
    result = await db.execute(select(Sensor).where(Sensor.sensor_id == sensor_id))
    sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    update_data = sensor_update.model_dump(exclude_unset=True)
    print(f"[DEBUG] Update data received: {update_data}")  # Debug log
    
    for field, value in update_data.items():
        setattr(sensor, field, value)
    
    await db.commit()
    await db.refresh(sensor)
    print(f"[DEBUG] Sensor after update: {sensor.sensor_type}")  # Debug log
    return sensor


@router.delete("/{sensor_id}", status_code=204)
async def delete_sensor(sensor_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a sensor."""
    result = await db.execute(select(Sensor).where(Sensor.sensor_id == sensor_id))
    sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    await db.delete(sensor)
    await db.commit()


@router.post("/data", response_model=dict, status_code=201)
async def receive_sensor_data(data: SensorDataInput, db: AsyncSession = Depends(get_db)):
    """Receive sensor data from devices."""
    # Check if sensor exists
    result = await db.execute(select(Sensor).where(Sensor.sensor_id == data.sensor_id))
    sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not registered")
    
    if not sensor.is_active:
        raise HTTPException(status_code=400, detail="Sensor is inactive")
    
    # Prepare reading data
    reading_data = {
        "sensor_id": data.sensor_id,
        "sensor_type": data.sensor_type,
        "status": data.status,
        "recorded_at": data.timestamp or datetime.utcnow(),
        "raw_data": data.model_dump(mode='json'),
    }
    
    # Add type-specific fields
    if data.sensor_type == "ultrasonic":
        reading_data.update({
            "water_level": data.water_level,
            "battery_level": data.battery_level,
            "signal_strength": data.signal_strength,
        })
    else:  # immersion
        reading_data.update({
            "water_detected": data.water_detected,
            "duration": data.duration,
            "severity": data.severity,
        })
    
    reading = SensorReading(**reading_data)
    db.add(reading)
    await db.commit()
    
    return {
        "success": True,
        "message": "Data received successfully",
        "reading_id": reading.id
    }


@router.get("/{sensor_id}/readings", response_model=SensorReadingList)
async def get_sensor_readings(
    sensor_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=10000),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db)
):
    """Get readings for a specific sensor with time range filtering."""
    # Check sensor exists
    result = await db.execute(select(Sensor).where(Sensor.sensor_id == sensor_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    # Build query
    query = select(SensorReading).where(SensorReading.sensor_id == sensor_id)
    
    if start_time:
        query = query.where(SensorReading.recorded_at >= start_time)
    if end_time:
        query = query.where(SensorReading.recorded_at <= end_time)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get paginated results
    offset = (page - 1) * limit
    query = query.order_by(desc(SensorReading.recorded_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": limit
    }


@router.get("/{sensor_id}/timeseries", response_model=SensorTimeSeries)
async def get_sensor_timeseries(
    sensor_id: str,
    field: str = Query("water_level", pattern="^(water_level|battery_level|signal_strength|water_detected)$"),
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db)
):
    """Get time series data for a sensor (for charting)."""
    # Check sensor exists
    result = await db.execute(select(Sensor).where(Sensor.sensor_id == sensor_id))
    sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    query = select(
        SensorReading.recorded_at,
        getattr(SensorReading, field)
    ).where(
        and_(
            SensorReading.sensor_id == sensor_id,
            SensorReading.recorded_at >= start_time
        )
    ).order_by(SensorReading.recorded_at)
    
    result = await db.execute(query)
    rows = result.all()
    
    data = [TimeSeriesPoint(timestamp=row[0], value=row[1]) for row in rows]
    
    return SensorTimeSeries(
        sensor_id=sensor_id,
        sensor_type=sensor.sensor_type.value,
        location=sensor.location,
        data=data
    )


@router.post("/webhook/{token}", response_model=dict, status_code=201)
async def receive_webhook_data(token: str, data: WebhookDataInput, db: AsyncSession = Depends(get_db)):
    """Receive sensor data via webhook token."""
    # Find sensor by webhook token
    result = await db.execute(select(Sensor).where(Sensor.webhook_token == token))
    sensor = result.scalar_one_or_none()
    
    if not sensor:
        raise HTTPException(status_code=404, detail="Invalid webhook token")
    
    if not sensor.is_active:
        raise HTTPException(status_code=400, detail="Sensor is inactive")
    
    # Prepare reading data
    reading_data = {
        "sensor_id": sensor.sensor_id,
        "sensor_type": sensor.sensor_type,
        "status": data.status,
        "recorded_at": data.timestamp or datetime.utcnow(),
        "raw_data": data.model_dump(mode='json'),
    }
    
    # Add type-specific fields
    if sensor.sensor_type == "ultrasonic":
        reading_data.update({
            "water_level": data.water_level,
            "battery_level": data.battery_level,
            "signal_strength": data.signal_strength,
        })
    else:  # immersion
        reading_data.update({
            "water_detected": data.water_detected,
            "duration": data.duration,
            "severity": data.severity,
        })
    
    reading = SensorReading(**reading_data)
    db.add(reading)
    await db.commit()
    
    return {
        "success": True,
        "message": "Data received successfully",
        "sensor_id": sensor.sensor_id,
        "reading_id": reading.id
    }


@router.get("/status/all", response_model=List[SensorStatus])
async def get_all_sensors_status(db: AsyncSession = Depends(get_db)):
    """Get current status of all sensors."""
    # Get all sensors with their latest reading
    query = select(Sensor).where(Sensor.is_active == True)
    result = await db.execute(query)
    sensors = result.scalars().all()
    
    offline_threshold = datetime.utcnow() - timedelta(minutes=60)
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
            sensor_type=sensor.sensor_type.value,
            location=sensor.location,
            status=latest_reading.status if latest_reading else "offline",
            last_reading=latest_reading.recorded_at if latest_reading else None,
            battery_level=latest_reading.battery_level if latest_reading else None,
            water_level=latest_reading.water_level if latest_reading else None,
            water_detected=latest_reading.water_detected if latest_reading else None,
            is_online=is_online
        ))
    
    return statuses
