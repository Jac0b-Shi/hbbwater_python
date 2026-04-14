"""Email service using WordPress mail API."""
import os
import warnings
from datetime import datetime
from typing import Optional

import httpx
import urllib3
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.system_config import get_notification_config_values

# 禁用 SSL 警告（内部 Docker 网络中使用 HTTP/禁用验证）
warnings.filterwarnings("ignore", message="Unverified HTTPS request")
warnings.filterwarnings("ignore", category=DeprecationWarning)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# WordPress API endpoint - 可通过环境变量配置
WORDPRESS_BASE_URL = os.getenv("WORDPRESS_URL", "http://wordpress")
WORDPRESS_MAIL_API = f"{WORDPRESS_BASE_URL}/wp-json/flood-monitor/v1/send-mail"
WORDPRESS_TEST_API = f"{WORDPRESS_BASE_URL}/wp-json/flood-monitor/v1/test-mail"
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "").strip()

# 创建 httpx 客户端配置 - 在 Docker 内部网络中禁用 SSL 验证
HTTPX_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def get_http_client():
    """Get configured HTTP client."""
    # 在 Docker 内部网络中使用 HTTP，不需要 SSL 验证
    return httpx.AsyncClient(
        timeout=HTTPX_TIMEOUT,
        verify=False,  # 禁用 SSL 验证（内部网络）
        http2=False    # 禁用 HTTP/2 避免兼容性问题
    )


async def send_email_via_wordpress(
    to: str,
    subject: str,
    message: str,
    headers: Optional[list] = None
) -> tuple[bool, str]:
    """Send email via WordPress API.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        async with get_http_client() as client:
            payload = {
                "to": to,
                "subject": subject,
                "message": message
            }
            if headers:
                payload["headers"] = headers
            
            response = await client.post(
                WORDPRESS_MAIL_API,
                json=payload,
                headers={"X-Internal-Token": INTERNAL_API_TOKEN} if INTERNAL_API_TOKEN else None,
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("success", False), result.get("message", "未知状态")
            else:
                return False, f"WordPress API 错误: HTTP {response.status_code}"
    except httpx.ConnectError as e:
        return False, f"无法连接到 WordPress 服务 ({WORDPRESS_BASE_URL}): {str(e)}"
    except httpx.TimeoutException:
        return False, "WordPress 邮件服务超时"
    except Exception as e:
        return False, f"邮件发送异常: {str(e)}"


async def send_test_email_via_wordpress(to: str) -> tuple[bool, str]:
    """Send test email via WordPress API.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        async with get_http_client() as client:
            response = await client.post(
                WORDPRESS_TEST_API,
                json={"to": to},
                headers={"X-Internal-Token": INTERNAL_API_TOKEN} if INTERNAL_API_TOKEN else None,
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("success", False), result.get("message", "测试邮件已发送")
            else:
                return False, f"WordPress API 错误: HTTP {response.status_code}"
    except httpx.ConnectError as e:
        return False, f"无法连接到 WordPress 服务 ({WORDPRESS_BASE_URL}): {str(e)}"
    except httpx.TimeoutException:
        return False, "WordPress 邮件服务超时"
    except Exception as e:
        return False, f"邮件发送异常: {str(e)}"


async def send_alert_email(
    control_db: AsyncSession,
    alert_type: str,
    severity: str,
    sensor_name: str,
    location: str,
    message: str,
    to_email: Optional[str] = None
) -> tuple[bool, str]:
    """Send alert notification email.
    
    Args:
        control_db: Control-plane database session
        alert_type: Type of alert (e.g., 'flood', 'offline')
        severity: Alert severity (e.g., 'critical', 'warning')
        sensor_name: Name of the sensor
        location: Location of the sensor
        message: Alert message
        to_email: Override recipient email (optional)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    # Get notification config
    config = await get_notification_config_values(control_db)
    
    # Check if email notifications are enabled
    if not config["email_enabled"]:
        return False, "邮件通知未启用"
    
    # Determine recipient
    recipient = to_email or config["smtp_user"]
    if not recipient:
        return False, "未配置收件人邮箱"
    
    # Build email subject
    severity_map = {
        "critical": "🔴 紧急",
        "warning": "🟡 警告", 
        "info": "🔵 信息"
    }
    severity_label = severity_map.get(severity, severity)
    
    alert_type_map = {
        "flood": "水浸告警",
        "offline": "设备离线",
        "battery": "电量告警",
        "threshold": "阈值告警"
    }
    alert_label = alert_type_map.get(alert_type, alert_type)
    
    subject = f"{severity_label} [{alert_label}] {sensor_name}"
    
    # Build email message
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    email_body = f"""水浸监测系统告警通知

═══════════════════════════════
告警信息
═══════════════════════════════
告警类型: {alert_label}
告警级别: {severity_label}
发生时间: {current_time}

═══════════════════════════════
设备信息
═══════════════════════════════
设备名称: {sensor_name}
安装位置: {location}

═══════════════════════════════
告警详情
═══════════════════════════════
{message}

═══════════════════════════════
此邮件由水浸监测系统自动发送
═══════════════════════════════
"""
    
    # Send email via WordPress
    return await send_email_via_wordpress(
        to=recipient,
        subject=subject,
        message=email_body
    )
