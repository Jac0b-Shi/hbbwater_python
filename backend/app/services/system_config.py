"""Shared helpers for system configuration and maintenance."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemConfig


async def get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    """Get config value by key."""
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    config = result.scalar_one_or_none()
    return config.config_value if config and config.config_value is not None else default


async def set_config_value(db: AsyncSession, key: str, value: str, description: str = "") -> None:
    """Create or update a config value by key."""
    result = await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
    config = result.scalar_one_or_none()

    if config:
        config.config_value = value
        if description:
            config.description = description
        config.updated_at = datetime.utcnow()
        await db.flush()
        return

    db.add(
        SystemConfig(
            config_key=key,
            config_value=value,
            description=description,
        )
    )
    await db.flush()


async def get_int_config(db: AsyncSession, key: str, default: int) -> int:
    value = await get_config_value(db, key, str(default))
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def get_bool_config(db: AsyncSession, key: str, default: bool) -> bool:
    value = await get_config_value(db, key, str(default).lower())
    return str(value).lower() == "true"


async def get_offline_timeout_minutes(db: AsyncSession, default: int = 60) -> int:
    """Return the effective offline timeout configured in minutes."""
    return await get_int_config(db, "offline_timeout_minutes", default)


async def get_database_stats(db: AsyncSession) -> dict[str, int]:
    """Collect record counts for operational tables."""
    tables = {
        "readings_count": "sensor_readings",
        "archive_count": "sensor_readings_archive",
        "hourly_count": "sensor_summary_hourly",
        "daily_count": "sensor_summary_daily",
    }
    stats: dict[str, int] = {}

    for field, table_name in tables.items():
        result = await db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        stats[field] = int(result.scalar() or 0)

    return stats


async def run_database_maintenance(db: AsyncSession) -> dict[str, Any]:
    """Move expired hot data into archive and optionally purge old archive data."""
    retention_days = await get_int_config(db, "data_retention_days", 14)
    archive_enabled = await get_bool_config(db, "archive_enabled", True)
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    archived_rows = 0
    deleted_rows = 0

    if archive_enabled:
        insert_result = await db.execute(
            text(
                """
                INSERT INTO sensor_readings_archive (
                    sensor_id, sensor_type, water_level, water_detected, duration, severity,
                    status, battery_level, signal_strength, raw_data, recorded_at, created_at
                )
                SELECT
                    sr.sensor_id, sr.sensor_type, sr.water_level, sr.water_detected, sr.duration, sr.severity,
                    sr.status, sr.battery_level, sr.signal_strength, sr.raw_data, sr.recorded_at, sr.created_at
                FROM sensor_readings sr
                WHERE sr.recorded_at < :cutoff
                  AND NOT EXISTS (
                    SELECT 1
                    FROM sensor_readings_archive sa
                    WHERE sa.sensor_id = sr.sensor_id
                      AND sa.recorded_at = sr.recorded_at
                      AND (
                        (sa.water_level <=> sr.water_level)
                        AND (sa.water_detected <=> sr.water_detected)
                        AND (sa.duration <=> sr.duration)
                        AND (sa.severity <=> sr.severity)
                      )
                  )
                """
            ),
            {"cutoff": cutoff},
        )
        archived_rows = int(insert_result.rowcount or 0)

    delete_result = await db.execute(
        text("DELETE FROM sensor_readings WHERE recorded_at < :cutoff"),
        {"cutoff": cutoff},
    )
    deleted_rows = int(delete_result.rowcount or 0)

    await db.commit()

    return {
        "retention_days": retention_days,
        "archive_enabled": archive_enabled,
        "cutoff": cutoff.isoformat(),
        "archived_rows": archived_rows,
        "deleted_rows": deleted_rows,
        "stats": await get_database_stats(db),
    }


async def optimize_database_tables(db: AsyncSession) -> dict[str, Any]:
    """Run OPTIMIZE TABLE on operational tables."""
    tables = [
        "sensor_readings",
        "sensor_readings_archive",
        "sensor_summary_hourly",
        "sensor_summary_daily",
        "alerts",
        "system_config",
    ]
    results = []

    for table_name in tables:
        optimize_result = await db.execute(text(f"OPTIMIZE TABLE {table_name}"))
        rows = optimize_result.fetchall()
        results.append({
            "table": table_name,
            "messages": [dict(row._mapping) for row in rows],
        })

    await db.commit()
    return {
        "optimized_tables": len(tables),
        "results": results,
        "stats": await get_database_stats(db),
    }
