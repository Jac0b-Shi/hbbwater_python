"""Python notification adapters for alert events."""

import smtplib
from email.message import EmailMessage

import httpx

from app.config import settings
from app.models import Alert, Sensor


async def send_alert_notification(alert: Alert, sensor: Sensor) -> None:
    if settings.webhook_url:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                settings.webhook_url,
                json={
                    "msgtype": "text",
                    "text": {"content": f"[{alert.severity}] {sensor.device_id}: {alert.message}"},
                },
            )

    if settings.smtp_host and settings.notify_email_to:
        message = EmailMessage()
        message["Subject"] = f"HBBWater alert: {sensor.device_id}"
        message["From"] = settings.smtp_from or settings.smtp_username
        message["To"] = settings.notify_email_to
        message.set_content(f"{alert.message}\n\nseverity={alert.severity}\nlocation={sensor.location}")
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)

