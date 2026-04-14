"""Alert management API routes."""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_control_db, get_db
from app.models import Alert, Sensor
from app.schemas import AlertCreate, AlertResponse, AlertResolveRequest
from app.services.email import send_alert_email
from app.services.text import repair_mojibake

router = APIRouter(prefix="/alerts", tags=["alerts"])


def serialize_alert(alert: Alert) -> dict:
    """Normalize alert content before returning it to the client."""
    return {
        "id": alert.id,
        "sensor_id": alert.sensor_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": repair_mojibake(alert.message) or "",
        "details": alert.details,
        "is_resolved": alert.is_resolved,
        "resolved_at": alert.resolved_at,
        "resolved_by": alert.resolved_by,
        "created_at": alert.created_at,
    }


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    sensor_id: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    is_resolved: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get alerts with filtering options."""
    query = select(Alert)
    
    if sensor_id:
        query = query.where(Alert.sensor_id == sensor_id)
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
    if severity:
        query = query.where(Alert.severity == severity)
    if is_resolved is not None:
        query = query.where(Alert.is_resolved == is_resolved)
    
    query = query.order_by(desc(Alert.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    return [serialize_alert(alert) for alert in result.scalars().all()]


@router.get("/active", response_model=List[AlertResponse])
async def get_active_alerts(
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all active (unresolved) alerts."""
    query = select(Alert).where(Alert.is_resolved == False)
    
    if severity:
        query = query.where(Alert.severity == severity)
    
    query = query.order_by(desc(Alert.created_at))
    result = await db.execute(query)
    return [serialize_alert(alert) for alert in result.scalars().all()]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific alert by ID."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return serialize_alert(alert)


@router.post("/", response_model=AlertResponse, status_code=201)
async def create_alert(
    alert: AlertCreate,
    db: AsyncSession = Depends(get_db),
    control_db: AsyncSession = Depends(get_control_db),
):
    """Create a new alert."""
    # Check if sensor exists
    result = await db.execute(select(Sensor).where(Sensor.sensor_id == alert.sensor_id))
    sensor = result.scalar_one_or_none()
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    db_alert = Alert(**alert.model_dump())
    db.add(db_alert)
    await db.commit()
    await db.refresh(db_alert)
    
    # Send email notification for critical alerts
    if alert.severity in ["critical", "warning"]:
        try:
            await send_alert_email(
                control_db=control_db,
                alert_type=alert.alert_type,
                severity=alert.severity,
                sensor_name=sensor.sensor_id,
                location=sensor.location or "未知位置",
                message=alert.message or f"检测到 {alert.alert_type} 告警"
            )
        except Exception:
            # Log error but don't fail the alert creation
            pass
    
    return serialize_alert(db_alert)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: int,
    resolve_data: AlertResolveRequest,
    db: AsyncSession = Depends(get_db)
):
    """Resolve an alert."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if alert.is_resolved:
        raise HTTPException(status_code=400, detail="Alert already resolved")
    
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = resolve_data.resolved_by
    
    await db.commit()
    await db.refresh(alert)
    return serialize_alert(alert)


@router.get("/stats/summary")
async def get_alert_stats(db: AsyncSession = Depends(get_db)):
    """Get alert statistics."""
    # Total alerts
    total_result = await db.execute(select(func.count()).select_from(Alert))
    total = total_result.scalar()
    
    # Active alerts by severity
    severity_query = select(
        Alert.severity,
        func.count().label("count")
    ).where(Alert.is_resolved == False).group_by(Alert.severity)
    
    severity_result = await db.execute(severity_query)
    severity_counts = {row[0]: row[1] for row in severity_result.all()}
    
    # Active alerts by type
    type_query = select(
        Alert.alert_type,
        func.count().label("count")
    ).where(Alert.is_resolved == False).group_by(Alert.alert_type)
    
    type_result = await db.execute(type_query)
    type_counts = {row[0]: row[1] for row in type_result.all()}
    
    # Today's alerts
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await db.execute(
        select(func.count()).where(Alert.created_at >= today)
    )
    today_count = today_result.scalar()
    
    return {
        "total_alerts": total,
        "active_alerts": sum(severity_counts.values()),
        "severity_breakdown": severity_counts,
        "type_breakdown": type_counts,
        "today_alerts": today_count
    }
