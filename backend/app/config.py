"""Application settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "校园水浸监测系统"
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://hbbwater:hbbwater@postgres:5432/hbbwater"

    jwt_secret: str = "change-this-course-demo-secret"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 720

    admin_username: str = "admin"
    admin_password: str = "admin123456"
    admin_email: str = "admin@example.local"

    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501,http://localhost:8000"

    mqtt_enabled: bool = True
    mqtt_host: str = "emqx"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_client_id: str = "hbbwater-python-backend"
    mqtt_data_topic: str = "hbbwater/+/+/data"
    mqtt_status_topic: str = "hbbwater/+/+/status"
    mqtt_reconnect_seconds: int = 5

    alert_cooldown_minutes: int = 30
    offline_timeout_seconds: int = 300

    webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    notify_email_to: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
