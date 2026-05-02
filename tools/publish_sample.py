"""Publish sample MQTT messages using Python."""

import argparse
import json
import random
import time
from datetime import datetime, timezone

from paho.mqtt import client as mqtt


def build_payload(device_id: str, sensor_type: str, value: float | None) -> dict:
    if sensor_type == "immersion":
        detected = bool(value) if value is not None else random.random() > 0.7
        return {
            "device_id": device_id,
            "type": "immersion",
            "value": detected,
            "water_detected": detected,
            "unit": "state",
            "battery": random.randint(60, 100),
            "rssi": random.randint(-85, -45),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    reading = value if value is not None else round(random.uniform(2, 28), 2)
    return {
        "device_id": device_id,
        "type": "ultrasonic",
        "value": reading,
        "unit": "cm",
        "battery": random.randint(60, 100),
        "rssi": random.randint(-85, -45),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish sample HBBWater MQTT telemetry.")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--device-id", default="US001")
    parser.add_argument("--type", choices=["ultrasonic", "immersion"], default="ultrasonic")
    parser.add_argument("--value", type=float, default=None)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        client = mqtt.Client()
    client.connect(args.host, args.port, keepalive=60)
    client.loop_start()
    topic = f"hbbwater/{args.type}/{args.device_id}/data"
    for _ in range(args.count):
        payload = build_payload(args.device_id, args.type, args.value)
        result = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
        result.wait_for_publish(timeout=5)
        print(f"{topic} {payload}")
        time.sleep(args.interval)
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
