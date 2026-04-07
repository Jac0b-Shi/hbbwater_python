"""Lightweight schema alignment for deployments without migrations."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def _index_exists(conn: AsyncConnection, index_name: str) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'sensors'
              AND index_name = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    )
    return result.scalar() is not None


async def _column_exists(conn: AsyncConnection, column_name: str) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'sensors'
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"column_name": column_name},
    )
    return result.scalar() is not None


async def _table_exists(conn: AsyncConnection, table_name: str) -> bool:
    result = await conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = :table_name
            LIMIT 1
            """
        ),
        {"table_name": table_name},
    )
    return result.scalar() is not None


async def ensure_runtime_schema(conn: AsyncConnection) -> None:
    """Add columns/indexes required by newer application versions."""
    if not await _table_exists(conn, "webhook_groups"):
        await conn.execute(
            text(
                """
                CREATE TABLE webhook_groups (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT NULL,
                    webhook_token VARCHAR(64) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_webhook_groups_token (webhook_token)
                )
                """
            )
        )
    if not await _column_exists(conn, "webhook_group_token"):
        await conn.execute(text("ALTER TABLE sensors ADD COLUMN webhook_group_token VARCHAR(64) NULL"))
    if not await _column_exists(conn, "webhook_group_id"):
        await conn.execute(text("ALTER TABLE sensors ADD COLUMN webhook_group_id INT NULL"))
    if not await _column_exists(conn, "device_imei"):
        await conn.execute(text("ALTER TABLE sensors ADD COLUMN device_imei VARCHAR(32) NULL"))
    if not await _index_exists(conn, "idx_webhook_group_token"):
        await conn.execute(text("CREATE INDEX idx_webhook_group_token ON sensors (webhook_group_token)"))
    if not await _index_exists(conn, "idx_sensors_webhook_group_id"):
        await conn.execute(text("CREATE INDEX idx_sensors_webhook_group_id ON sensors (webhook_group_id)"))
    if not await _index_exists(conn, "idx_device_imei"):
        await conn.execute(text("CREATE INDEX idx_device_imei ON sensors (device_imei)"))
    await conn.execute(
        text(
            """
            INSERT INTO webhook_groups (name, description, webhook_token, is_active, created_at, updated_at)
            SELECT CONCAT('Legacy Group ', sensors.webhook_group_token),
                   'Migrated from legacy sensor-bound group token',
                   sensors.webhook_group_token,
                   TRUE,
                   CURRENT_TIMESTAMP,
                   CURRENT_TIMESTAMP
            FROM sensors
            LEFT JOIN webhook_groups ON webhook_groups.webhook_token = sensors.webhook_group_token
            WHERE sensors.webhook_group_token IS NOT NULL
              AND sensors.webhook_group_token <> ''
              AND webhook_groups.id IS NULL
            GROUP BY sensors.webhook_group_token
            """
        )
    )
    await conn.execute(
        text(
            """
            UPDATE sensors
            JOIN webhook_groups ON webhook_groups.webhook_token = sensors.webhook_group_token
            SET sensors.webhook_group_id = webhook_groups.id
            WHERE sensors.webhook_group_id IS NULL
              AND sensors.webhook_group_token IS NOT NULL
              AND sensors.webhook_group_token <> ''
            """
        )
    )
