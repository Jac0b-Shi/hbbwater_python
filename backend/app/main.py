"""FastAPI entry point."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config import settings
from app.database import SessionLocal, init_db
from app.mqtt.client import MqttWorker
from app.services.seed import seed_defaults


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await seed_defaults(session)

    mqtt_worker = MqttWorker(asyncio.get_running_loop())
    app.state.mqtt_worker = mqtt_worker
    mqtt_worker.start()
    yield
    mqtt_worker.stop()


app = FastAPI(
    title=settings.app_name,
    description="纯 Python + MQTT 的校园水浸监测系统 API",
    version="2.0.0-python",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {
        "status": "healthy",
        "service": "hbbwater-python-api",
        "mqtt_enabled": settings.mqtt_enabled,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["root"])
async def root() -> dict:
    return {"name": settings.app_name, "docs": "/docs", "health": "/health"}


app.include_router(router)
