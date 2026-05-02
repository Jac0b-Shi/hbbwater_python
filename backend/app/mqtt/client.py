"""Background MQTT subscriber implemented in Python."""

import asyncio
import json
import logging
import threading
import time

from paho.mqtt import client as mqtt

from app.config import settings
from app.database import SessionLocal
from app.services.ingestion import ingest_payload

logger = logging.getLogger(__name__)


class MqttWorker:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._client: mqtt.Client | None = None

    def start(self) -> None:
        if not settings.mqtt_enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="mqtt-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                logger.exception("Failed to disconnect MQTT client")
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def _new_client(self) -> mqtt.Client:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=settings.mqtt_client_id)
        except AttributeError:
            client = mqtt.Client(client_id=settings.mqtt_client_id)
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        return client

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._client = self._new_client()
            try:
                self._client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
                self._client.loop_forever()
            except Exception:
                logger.exception("MQTT connection failed")
                time.sleep(settings.mqtt_reconnect_seconds)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        code = getattr(reason_code, "value", reason_code)
        if code == 0:
            client.subscribe(settings.mqtt_data_topic)
            client.subscribe(settings.mqtt_status_topic)
            logger.info("MQTT connected and subscribed")
        else:
            logger.warning("MQTT connect returned %s", reason_code)

    def _on_message(self, client, userdata, message) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            future = asyncio.run_coroutine_threadsafe(self._handle_message(payload, message.topic), self._loop)
            future.add_done_callback(self._log_message_result)
        except Exception:
            logger.exception("Failed to process MQTT message from %s", getattr(message, "topic", "unknown"))

    async def _handle_message(self, payload: dict, topic: str) -> None:
        async with SessionLocal() as session:
            await ingest_payload(session, payload, topic)

    def _log_message_result(self, future) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("Failed to process MQTT message")
