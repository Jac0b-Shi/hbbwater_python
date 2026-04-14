"""Configuration management router."""
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_business_db, get_control_db
from app.services.business_profiles import (
    activate_business_profile,
    get_business_profiles_state,
    save_business_profile,
    serialize_business_profile,
    test_business_profile_payload,
)
from app.services.internal_auth import verify_internal_api_token
from app.services.system_config import (
    get_bool_config,
    get_config_value,
    get_database_stats,
    get_int_config,
    get_notification_config_values,
    optimize_database_tables,
    run_database_maintenance,
    set_config_value,
)

router = APIRouter(prefix="/config", tags=["config"])


class SystemConfigResponse(BaseModel):
    data_retention_days: int = 14
    offline_timeout_minutes: int = 60
    alert_cooldown_minutes: int = 30
    archive_enabled: bool = True
    summary_enabled: bool = True

    class Config:
        from_attributes = True


class NotificationConfigResponse(BaseModel):
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password_set: bool = False
    smtp_ssl: bool = True
    webhook_enabled: bool = False
    webhook_url: str = ""

    class Config:
        from_attributes = True


class SystemConfigUpdate(BaseModel):
    data_retention_days: Optional[int] = None
    offline_timeout_minutes: Optional[int] = None
    alert_cooldown_minutes: Optional[int] = None
    archive_enabled: Optional[bool] = None
    summary_enabled: Optional[bool] = None


class NotificationConfigUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    clear_smtp_password: Optional[bool] = None
    smtp_ssl: Optional[bool] = None
    webhook_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None


class TestEmailRequest(BaseModel):
    to: Optional[str] = None


class BusinessDatabaseProfilePayload(BaseModel):
    id: Optional[int] = None
    profile_key: Optional[str] = Field(default=None, max_length=64)
    display_name: str = Field(..., min_length=2, max_length=100)
    dialect: str = Field(default="mysql", pattern="^(mysql|dm|sqlite)$")
    driver: Optional[str] = Field(default=None, max_length=50)
    host: Optional[str] = Field(default="", max_length=255)
    port: Optional[str] = Field(default="", max_length=16)
    service_name: Optional[str] = Field(default="", max_length=128)
    database_name: str = Field(..., min_length=1, max_length=255)
    username: str = Field(default="", max_length=255)
    password: Optional[str] = Field(default=None, max_length=255)
    clear_password: Optional[bool] = False
    dm_home: Optional[str] = Field(default="", max_length=255)
    dm_svc_path: Optional[str] = Field(default="", max_length=255)
    auto_create_schema: bool = False

@router.get("/system", response_model=SystemConfigResponse)
async def get_system_config(control_db: AsyncSession = Depends(get_control_db)):
    """Get control-plane system configuration."""
    return SystemConfigResponse(
        data_retention_days=await get_int_config(control_db, "data_retention_days", 14),
        offline_timeout_minutes=await get_int_config(control_db, "offline_timeout_minutes", 60),
        alert_cooldown_minutes=await get_int_config(control_db, "alert_cooldown_minutes", 30),
        archive_enabled=await get_bool_config(control_db, "archive_enabled", True),
        summary_enabled=await get_bool_config(control_db, "summary_enabled", True),
    )


@router.post("/system")
async def update_system_config(
    config: SystemConfigUpdate,
    control_db: AsyncSession = Depends(get_control_db),
):
    """Update control-plane system configuration."""
    try:
        if config.data_retention_days is not None:
            await set_config_value(control_db, "data_retention_days", str(config.data_retention_days), "热数据保留天数")
        if config.offline_timeout_minutes is not None:
            await set_config_value(control_db, "offline_timeout_minutes", str(config.offline_timeout_minutes), "离线判定时间(分钟)")
        if config.alert_cooldown_minutes is not None:
            await set_config_value(control_db, "alert_cooldown_minutes", str(config.alert_cooldown_minutes), "告警冷却时间(分钟)")
        if config.archive_enabled is not None:
            await set_config_value(control_db, "archive_enabled", str(config.archive_enabled).lower(), "自动归档")
        if config.summary_enabled is not None:
            await set_config_value(control_db, "summary_enabled", str(config.summary_enabled).lower(), "数据统计")
        await control_db.commit()
        return {"message": "系统配置已保存"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存失败: {exc}") from exc


@router.get("/notification", response_model=NotificationConfigResponse)
async def get_notification_config(control_db: AsyncSession = Depends(get_control_db)):
    """Get notification configuration from the control DB."""
    values = await get_notification_config_values(control_db)
    return NotificationConfigResponse(**values)


@router.post("/notification")
async def update_notification_config(
    config: NotificationConfigUpdate,
    control_db: AsyncSession = Depends(get_control_db),
):
    """Update notification configuration."""
    try:
        if config.email_enabled is not None:
            await set_config_value(control_db, "email_enabled", str(config.email_enabled).lower(), "邮件通知开关")
        if config.smtp_host is not None:
            await set_config_value(control_db, "smtp_host", config.smtp_host, "SMTP服务器")
        if config.smtp_port is not None:
            await set_config_value(control_db, "smtp_port", str(config.smtp_port), "SMTP端口")
        if config.smtp_user is not None:
            await set_config_value(control_db, "smtp_user", config.smtp_user, "发件人邮箱")
        if config.smtp_password is not None:
            await set_config_value(control_db, "smtp_password", config.smtp_password, "SMTP密码")
        elif config.clear_smtp_password:
            await set_config_value(control_db, "smtp_password", "", "SMTP密码")
        if config.smtp_ssl is not None:
            await set_config_value(control_db, "smtp_ssl", str(config.smtp_ssl).lower(), "使用SSL/TLS")
        if config.webhook_enabled is not None:
            await set_config_value(control_db, "webhook_enabled", str(config.webhook_enabled).lower(), "Webhook通知开关")
        if config.webhook_url is not None:
            await set_config_value(control_db, "webhook_url", config.webhook_url, "Webhook URL")
        await control_db.commit()
        return {"message": "通知配置已保存"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存失败: {exc}") from exc


@router.post("/notification/test-email")
async def test_email_notification(
    request: TestEmailRequest,
    control_db: AsyncSession = Depends(get_control_db),
):
    """Send a test email notification."""
    from app.services.email import send_test_email_via_wordpress

    notify_config = await get_notification_config_values(control_db)
    if not notify_config["email_enabled"]:
        raise HTTPException(status_code=400, detail="邮件通知未启用")

    recipient = request.to or notify_config["smtp_user"]
    if not recipient:
        raise HTTPException(status_code=400, detail="未配置发件人邮箱，请提供目标邮箱")

    import re

    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", recipient):
        raise HTTPException(status_code=400, detail="邮箱格式无效")

    success, message = await send_test_email_via_wordpress(recipient)
    if success:
        return {"message": f"测试邮件已发送到 {recipient}: {message}"}

    import smtplib
    from email.mime.text import MIMEText

    if not notify_config["smtp_host"] or not notify_config["smtp_password"]:
        raise HTTPException(status_code=500, detail=f"WordPress 邮件服务失败: {message}")

    try:
        msg = MIMEText("这是一封测试邮件，来自水浸监测系统。", "plain", "utf-8")
        msg["Subject"] = "[水浸监测系统] 邮件测试"
        msg["From"] = notify_config["smtp_user"]
        msg["To"] = recipient

        if notify_config["smtp_port"] == 465:
            server = smtplib.SMTP_SSL(notify_config["smtp_host"], notify_config["smtp_port"])
        else:
            server = smtplib.SMTP(notify_config["smtp_host"], notify_config["smtp_port"])
            if notify_config["smtp_ssl"]:
                server.starttls()

        server.login(notify_config["smtp_user"], notify_config["smtp_password"])
        server.sendmail(notify_config["smtp_user"], [recipient], msg.as_string())
        server.quit()
        return {"message": f"测试邮件已通过 SMTP 发送到 {recipient}"}
    except Exception as smtp_error:
        raise HTTPException(
            status_code=500,
            detail=f"邮件发送失败 - WordPress: {message}, SMTP: {smtp_error}",
        ) from smtp_error


@router.get("/notification/mail-config")
async def get_mail_config_for_wordpress(
    _: None = Depends(verify_internal_api_token),
    control_db: AsyncSession = Depends(get_control_db),
):
    """Get mail configuration for the WordPress plugin."""
    notify_config = await get_notification_config_values(control_db)
    if not notify_config["email_enabled"]:
        return {"enabled": False, "message": "邮件通知未启用"}

    return {
        "enabled": True,
        "smtp_host": notify_config["smtp_host"],
        "smtp_port": notify_config["smtp_port"],
        "smtp_user": notify_config["smtp_user"],
        "smtp_pass": notify_config["smtp_password"],
        "smtp_ssl": notify_config["smtp_ssl"],
        "from_email": notify_config["smtp_user"],
    }


@router.post("/notification/test-webhook")
async def test_webhook_notification(control_db: AsyncSession = Depends(get_control_db)):
    """Send a test webhook notification."""
    notify_config = await get_notification_config_values(control_db)
    if not notify_config["webhook_enabled"]:
        raise HTTPException(status_code=400, detail="Webhook 通知未启用")
    if not notify_config["webhook_url"]:
        raise HTTPException(status_code=400, detail="Webhook URL 未配置")

    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "msg_type": "text",
                "content": {"text": "🧪 这是来自水浸监测系统的测试消息\n\n时间: " + str(datetime.utcnow())},
            }
            response = await client.post(notify_config["webhook_url"], json=payload, timeout=10.0)
            response.raise_for_status()
        return {"message": "测试 Webhook 已发送"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Webhook 发送失败: {exc}") from exc


@router.get("/business-database")
async def get_business_database_catalog(control_db: AsyncSession = Depends(get_control_db)):
    """List stored business DB profiles and current runtime state."""
    return await get_business_profiles_state(control_db)


@router.post("/business-database/profiles")
async def save_business_database_profile(
    payload: BusinessDatabaseProfilePayload,
    control_db: AsyncSession = Depends(get_control_db),
):
    """Create or update a business DB profile."""
    try:
        profile = await save_business_profile(control_db, payload.model_dump())
        return {"message": "业务数据库配置已保存", "profile": serialize_business_profile(profile)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存业务数据库配置失败: {exc}") from exc


@router.post("/business-database/profiles/test")
async def test_business_database_profile(
    payload: BusinessDatabaseProfilePayload,
    control_db: AsyncSession = Depends(get_control_db),
):
    """Validate a business DB profile without activating it."""
    try:
        result = await test_business_profile_payload(control_db, payload.model_dump())
        return {"message": "数据库连接测试成功", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据库连接测试失败: {exc}") from exc


@router.post("/business-database/profiles/{profile_id}/activate")
async def activate_business_database_profile(
    profile_id: int,
    control_db: AsyncSession = Depends(get_control_db),
):
    """Activate a stored business DB profile and hot-swap the business runtime."""
    try:
        profile = await activate_business_profile(control_db, profile_id)
        return {
            "message": f"已切换业务数据库到 {profile.display_name}",
            "profile": serialize_business_profile(profile),
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"切换业务数据库失败: {exc}") from exc


@router.get("/database/stats")
async def get_database_statistics(business_db: AsyncSession = Depends(get_business_db)):
    """Get record counts for business tables shown in settings."""
    return await get_database_stats(business_db)


@router.post("/database/maintenance")
async def execute_database_maintenance(
    business_db: AsyncSession = Depends(get_business_db),
    control_db: AsyncSession = Depends(get_control_db),
):
    """Archive and purge expired business data according to control-plane settings."""
    try:
        result = await run_database_maintenance(business_db, control_db)
        return {
            "message": f"维护完成，归档 {result['archived_rows']} 条，清理 {result['deleted_rows']} 条热数据",
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"维护失败: {exc}") from exc


@router.post("/database/optimize")
async def execute_database_optimize(business_db: AsyncSession = Depends(get_business_db)):
    """Optimize operational business tables."""
    try:
        result = await optimize_database_tables(business_db)
        return {
            "message": f"已优化 {result['optimized_tables']} 张数据表",
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"优化失败: {exc}") from exc
