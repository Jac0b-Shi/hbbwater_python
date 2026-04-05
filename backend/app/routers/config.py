"""Configuration management router."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx

from app.database import get_db
from app.models import SystemConfig

router = APIRouter(prefix="/config", tags=["config"])


class ConfigItem(BaseModel):
    key: str
    value: str


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
    smtp_password: str = ""
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
    smtp_ssl: Optional[bool] = None
    webhook_enabled: Optional[bool] = None
    webhook_url: Optional[str] = None


async def get_config_value(db: AsyncSession, key: str, default: str = "") -> str:
    """Get config value by key."""
    result = await db.execute(select(SystemConfig).filter(SystemConfig.config_key == key))
    config = result.scalar_one_or_none()
    return config.config_value if config else default


async def set_config_value(db: AsyncSession, key: str, value: str, description: str = ""):
    """Set config value by key."""
    result = await db.execute(select(SystemConfig).filter(SystemConfig.config_key == key))
    config = result.scalar_one_or_none()
    if config:
        config.config_value = value
        config.updated_at = datetime.utcnow()
    else:
        config = SystemConfig(
            config_key=key,
            config_value=value,
            description=description
        )
        db.add(config)
    await db.commit()


@router.get("/system", response_model=SystemConfigResponse)
async def get_system_config(db: AsyncSession = Depends(get_db)):
    """Get system configuration."""
    return SystemConfigResponse(
        data_retention_days=int(await get_config_value(db, "data_retention_days", "14")),
        offline_timeout_minutes=int(await get_config_value(db, "offline_timeout_minutes", "60")),
        alert_cooldown_minutes=int(await get_config_value(db, "alert_cooldown_minutes", "30")),
        archive_enabled=(await get_config_value(db, "archive_enabled", "true")).lower() == "true",
        summary_enabled=(await get_config_value(db, "summary_enabled", "true")).lower() == "true"
    )


@router.post("/system")
async def update_system_config(
    config: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update system configuration."""
    try:
        if config.data_retention_days is not None:
            await set_config_value(db, "data_retention_days", str(config.data_retention_days), "热数据保留天数")
        if config.offline_timeout_minutes is not None:
            await set_config_value(db, "offline_timeout_minutes", str(config.offline_timeout_minutes), "离线判定时间(分钟)")
        if config.alert_cooldown_minutes is not None:
            await set_config_value(db, "alert_cooldown_minutes", str(config.alert_cooldown_minutes), "告警冷却时间(分钟)")
        if config.archive_enabled is not None:
            await set_config_value(db, "archive_enabled", str(config.archive_enabled).lower(), "自动归档")
        if config.summary_enabled is not None:
            await set_config_value(db, "summary_enabled", str(config.summary_enabled).lower(), "数据统计")
        return {"message": "系统配置已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/notification", response_model=NotificationConfigResponse)
async def get_notification_config(db: AsyncSession = Depends(get_db)):
    """Get notification configuration."""
    return NotificationConfigResponse(
        email_enabled=(await get_config_value(db, "email_enabled", "false")).lower() == "true",
        smtp_host=await get_config_value(db, "smtp_host", ""),
        smtp_port=int(await get_config_value(db, "smtp_port", "587")),
        smtp_user=await get_config_value(db, "smtp_user", ""),
        smtp_password=await get_config_value(db, "smtp_password", ""),
        smtp_ssl=(await get_config_value(db, "smtp_ssl", "true")).lower() == "true",
        webhook_enabled=(await get_config_value(db, "webhook_enabled", "false")).lower() == "true",
        webhook_url=await get_config_value(db, "webhook_url", "")
    )


@router.post("/notification")
async def update_notification_config(
    config: NotificationConfigUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update notification configuration."""
    try:
        if config.email_enabled is not None:
            await set_config_value(db, "email_enabled", str(config.email_enabled).lower(), "邮件通知开关")
        if config.smtp_host is not None:
            await set_config_value(db, "smtp_host", config.smtp_host, "SMTP服务器")
        if config.smtp_port is not None:
            await set_config_value(db, "smtp_port", str(config.smtp_port), "SMTP端口")
        if config.smtp_user is not None:
            await set_config_value(db, "smtp_user", config.smtp_user, "发件人邮箱")
        if config.smtp_password is not None:
            await set_config_value(db, "smtp_password", config.smtp_password, "SMTP密码")
        if config.smtp_ssl is not None:
            await set_config_value(db, "smtp_ssl", str(config.smtp_ssl).lower(), "使用SSL/TLS")
        if config.webhook_enabled is not None:
            await set_config_value(db, "webhook_enabled", str(config.webhook_enabled).lower(), "Webhook通知开关")
        if config.webhook_url is not None:
            await set_config_value(db, "webhook_url", config.webhook_url, "Webhook URL")
        return {"message": "通知配置已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


class TestEmailRequest(BaseModel):
    to: Optional[str] = None  # 目标邮箱，如果不传则使用配置的邮箱


@router.post("/notification/test-email")
async def test_email_notification(
    request: TestEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a test email notification.
    
    Args:
        request.to: 目标邮箱地址，可选，默认使用配置的邮箱
    """
    from app.services.email import send_test_email_via_wordpress
    
    notify_config = await get_notification_config(db)
    
    if not notify_config.email_enabled:
        raise HTTPException(status_code=400, detail="邮件通知未启用")
    
    # 使用传入的目标邮箱或配置的邮箱
    recipient = request.to or notify_config.smtp_user
    if not recipient:
        raise HTTPException(status_code=400, detail="未配置发件人邮箱，请提供目标邮箱")
    
    # 验证邮箱格式
    import re
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', recipient):
        raise HTTPException(status_code=400, detail="邮箱格式无效")
    
    # 使用 WordPress 邮件服务发送测试邮件
    success, message = await send_test_email_via_wordpress(recipient)
    
    if success:
        return {"message": f"测试邮件已发送到 {recipient}: {message}"}
    else:
        # WordPress 失败，尝试直接 SMTP
        import smtplib
        from email.mime.text import MIMEText
        
        if not notify_config.smtp_host or not notify_config.smtp_password:
            raise HTTPException(status_code=500, detail=f"WordPress 邮件服务失败: {message}")
        
        try:
            msg = MIMEText("这是一封测试邮件，来自水浸监测系统。", "plain", "utf-8")
            msg["Subject"] = "[水浸监测系统] 邮件测试"
            msg["From"] = notify_config.smtp_user
            msg["To"] = recipient
            
            if notify_config.smtp_port == 465:
                server = smtplib.SMTP_SSL(notify_config.smtp_host, notify_config.smtp_port)
            else:
                server = smtplib.SMTP(notify_config.smtp_host, notify_config.smtp_port)
                if notify_config.smtp_ssl:
                    server.starttls()
            
            server.login(notify_config.smtp_user, notify_config.smtp_password)
            server.sendmail(notify_config.smtp_user, [recipient], msg.as_string())
            server.quit()
            
            return {"message": f"测试邮件已通过 SMTP 发送到 {recipient}"}
        except Exception as smtp_error:
            raise HTTPException(status_code=500, detail=f"邮件发送失败 - WordPress: {message}, SMTP: {str(smtp_error)}")


async def send_mail_via_wordpress(to: str, subject: str, message: str) -> bool:
    """Send email via WordPress API."""
    from app.services.email import send_email_via_wordpress
    success, _ = await send_email_via_wordpress(to, subject, message)
    return success


@router.get("/notification/mail-config")
async def get_mail_config_for_wordpress(db: AsyncSession = Depends(get_db)):
    """Get mail configuration for WordPress plugin.
    
    This endpoint is called by WordPress to get SMTP settings.
    """
    notify_config = await get_notification_config(db)
    
    if not notify_config.email_enabled:
        return {
            "enabled": False,
            "message": "邮件通知未启用"
        }
    
    return {
        "enabled": True,
        "smtp_host": notify_config.smtp_host,
        "smtp_port": notify_config.smtp_port,
        "smtp_user": notify_config.smtp_user,
        "smtp_pass": notify_config.smtp_password,
        "smtp_ssl": notify_config.smtp_ssl,
        "from_email": notify_config.smtp_user  # 使用用户名作为发件人
    }


@router.post("/notification/test-webhook")
async def test_webhook_notification(db: AsyncSession = Depends(get_db)):
    """Send a test webhook notification."""
    import httpx
    
    notify_config = await get_notification_config(db)
    
    if not notify_config.webhook_enabled:
        raise HTTPException(status_code=400, detail="Webhook 通知未启用")
    
    if not notify_config.webhook_url:
        raise HTTPException(status_code=400, detail="Webhook URL 未配置")
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": "🧪 这是来自水浸监测系统的测试消息\n\n时间: " + str(datetime.utcnow())
                }
            }
            response = await client.post(
                notify_config.webhook_url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()
        return {"message": "测试 Webhook 已发送"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook 发送失败: {str(e)}")
