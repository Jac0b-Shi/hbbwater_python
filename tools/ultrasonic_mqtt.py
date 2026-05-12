#!/usr/bin/env python3
"""Read an L07A ultrasonic sensor and publish readings to HBBWater MQTT."""

from __future__ import annotations

import argparse
import json
import socket
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import serial
from paho.mqtt import client as mqtt


DEFAULT_PORT = "/dev/ttyS2"
DEFAULT_BAUDRATE = 115200
DEFAULT_MAX_DISTANCE_MM = 3000
DEFAULT_WINDOW_SIZE = 8
DEFAULT_SAMPLE_INTERVAL = 0.1
DEFAULT_PUBLISH_INTERVAL = 5.0
DEFAULT_TRIM_RATIO = 0.1


class UltrasonicSensor:
    """L07A UART sensor reader.

    Protocol: [0xFF, Data_H, Data_L, SUM], where SUM is the low byte of
    0xFF + Data_H + Data_L. The sensor is triggered by sending 0x01.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = 1.0,
        max_valid_distance_mm: int = DEFAULT_MAX_DISTANCE_MM,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.max_valid_distance_mm = max_valid_distance_mm
        self.ser: serial.Serial | None = None

    def open(self) -> None:
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )

    def close(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def __enter__(self) -> "UltrasonicSensor":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.close()
        return False

    def trigger_measurement(self) -> bool:
        if not self.ser or not self.ser.is_open:
            return False
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.ser.write(b"\x01")
            self.ser.flush()
            return True
        except serial.SerialException:
            return False

    def parse_data(self, data: bytes) -> tuple[int | None, bool, str | None]:
        if len(data) < 4:
            return None, False, f"data too short: expected at least 4 bytes, got {len(data)}"

        start_idx = -1
        for idx in range(len(data) - 3):
            if data[idx] == 0xFF:
                start_idx = idx
                break

        if start_idx < 0 or start_idx + 4 > len(data):
            return None, False, "no valid 0xFF frame header found"

        header = data[start_idx]
        data_h = data[start_idx + 1]
        data_l = data[start_idx + 2]
        checksum = data[start_idx + 3]
        expected = (header + data_h + data_l) & 0xFF
        if checksum != expected:
            return None, False, f"checksum mismatch: expected 0x{expected:02X}, got 0x{checksum:02X}"

        distance = (data_h << 8) | data_l
        if distance == 0xFFFE:
            return None, False, "same-frequency interference"
        if distance == 0xFFFD:
            return None, False, "no object detected"
        if distance > self.max_valid_distance_mm:
            return None, False, f"distance out of range: {distance}mm > {self.max_valid_distance_mm}mm"
        return distance, True, None

    def read_raw(self, wait_time: float = 0.05) -> tuple[int | None, bool, str | None]:
        if not self.trigger_measurement():
            return None, False, "failed to send trigger byte"
        time.sleep(wait_time)
        if not self.ser:
            return None, False, "serial port is not open"
        try:
            data = self.ser.read(self.ser.in_waiting or 4)
        except serial.SerialException as exc:
            return None, False, f"serial error: {exc}"
        return self.parse_data(data)


def compute_trimmed_mean(samples: list[int], trim_ratio: float = DEFAULT_TRIM_RATIO) -> tuple[int | None, bool]:
    if not samples or trim_ratio < 0 or trim_ratio >= 0.5:
        return None, False
    ordered = sorted(samples)
    trim_count = int(len(ordered) * trim_ratio)
    if trim_count * 2 >= len(ordered):
        trim_count = 0
    trimmed = ordered[trim_count : len(ordered) - trim_count] or ordered
    return (sum(trimmed) + len(trimmed) // 2) // len(trimmed), True


@dataclass(frozen=True)
class WindowStats:
    count: int
    minimum: int
    maximum: int
    average: int
    elapsed_ms: float


class SampleWindow:
    def __init__(self, size: int = DEFAULT_WINDOW_SIZE, trim_ratio: float = DEFAULT_TRIM_RATIO) -> None:
        self.size = size
        self.trim_ratio = trim_ratio
        self.samples: deque[int] = deque(maxlen=size)
        self.start_time: float | None = None

    def reset(self) -> None:
        self.samples.clear()
        self.start_time = None

    def add_sample(self, value: int) -> bool:
        if self.start_time is None:
            self.start_time = time.time()
        self.samples.append(value)
        return len(self.samples) >= self.size

    def get_filtered_value(self) -> tuple[int | None, bool]:
        return compute_trimmed_mean(list(self.samples), self.trim_ratio)

    def stats(self) -> WindowStats:
        samples = list(self.samples)
        elapsed_ms = 0.0 if self.start_time is None else (time.time() - self.start_time) * 1000
        return WindowStats(
            count=len(samples),
            minimum=min(samples) if samples else 0,
            maximum=max(samples) if samples else 0,
            average=sum(samples) // len(samples) if samples else 0,
            elapsed_ms=elapsed_ms,
        )


def new_mqtt_client(client_id: str, username: str | None, password: str | None) -> mqtt.Client:
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    except AttributeError:
        client = mqtt.Client(client_id=client_id)
    if username:
        client.username_pw_set(username, password)
    return client


def build_payload(
    *,
    device_id: str,
    distance_mm: int,
    threshold_mm: int | None,
    stats: WindowStats,
    source: str,
) -> dict[str, Any]:
    high_water = distance_mm <= threshold_mm if threshold_mm is not None else None
    payload: dict[str, Any] = {
        "device_id": device_id,
        "type": "ultrasonic",
        "value": distance_mm,
        "water_level": distance_mm,
        "unit": "mm",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "value_kind": "distance_to_surface",
        "sample_count": stats.count,
        "raw_min_mm": stats.minimum,
        "raw_max_mm": stats.maximum,
        "raw_avg_mm": stats.average,
        "window_elapsed_ms": round(stats.elapsed_ms, 1),
    }
    if threshold_mm is not None:
        payload["threshold_mm"] = threshold_mm
        payload["high_water"] = high_water
        payload["water_detected"] = high_water
    return payload


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish L07A ultrasonic readings to HBBWater MQTT.")
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"Serial port, default: {DEFAULT_PORT}")
    parser.add_argument("--baudrate", type=positive_int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--broker", default="localhost", help="MQTT broker host")
    parser.add_argument("--mqtt-port", type=positive_int, default=1883)
    parser.add_argument("--mqtt-username")
    parser.add_argument("--mqtt-password")
    parser.add_argument("--device-id", default=f"{socket.gethostname()}-ultrasonic")
    parser.add_argument("--topic", help="MQTT topic. Default: hbbwater/ultrasonic/{device_id}/data")
    parser.add_argument("--client-id", help="MQTT client id. Default: ultrasonic-mqtt-{device_id}")
    parser.add_argument("--interval", type=float, default=DEFAULT_PUBLISH_INTERVAL, help="Publish interval in seconds")
    parser.add_argument("--sample-interval", type=float, default=DEFAULT_SAMPLE_INTERVAL)
    parser.add_argument("--window-size", type=positive_int, default=DEFAULT_WINDOW_SIZE)
    parser.add_argument("--trim-ratio", type=float, default=DEFAULT_TRIM_RATIO)
    parser.add_argument("--max-distance-mm", type=positive_int, default=DEFAULT_MAX_DISTANCE_MM)
    parser.add_argument("--threshold-mm", type=positive_int)
    parser.add_argument("--count", type=int, default=0, help="Number of MQTT messages to publish. 0 means forever")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval <= 0 or args.sample_interval <= 0:
        raise SystemExit("--interval and --sample-interval must be greater than 0")
    if args.trim_ratio < 0 or args.trim_ratio >= 0.5:
        raise SystemExit("--trim-ratio must be >= 0 and < 0.5")

    topic = args.topic or f"hbbwater/ultrasonic/{args.device_id}/data"
    client_id = args.client_id or f"ultrasonic-mqtt-{args.device_id}"
    source = f"{socket.gethostname()}:{args.port}"

    client = new_mqtt_client(client_id, args.mqtt_username, args.mqtt_password)
    client.connect(args.broker, args.mqtt_port, keepalive=60)
    client.loop_start()

    published = 0
    consecutive_errors = 0
    window = SampleWindow(args.window_size, args.trim_ratio)

    try:
        with UltrasonicSensor(
            args.port,
            baudrate=args.baudrate,
            max_valid_distance_mm=args.max_distance_mm,
        ) as sensor:
            print(
                f"publishing {args.port} -> mqtt://{args.broker}:{args.mqtt_port}/{topic} "
                f"device_id={args.device_id}"
            )
            while args.count <= 0 or published < args.count:
                cycle_start = time.time()
                window.reset()
                last_error = None

                while len(window.samples) < args.window_size and time.time() - cycle_start < args.interval:
                    distance, success, error = sensor.read_raw()
                    if success and distance is not None:
                        consecutive_errors = 0
                        window.add_sample(distance)
                        if args.verbose:
                            print(f"sample {distance}mm ({len(window.samples)}/{args.window_size})")
                    else:
                        consecutive_errors += 1
                        last_error = error
                        if args.verbose or consecutive_errors <= 3:
                            print(f"read error: {error}")
                        if consecutive_errors > 10:
                            raise RuntimeError(f"too many consecutive sensor read errors: {error}")
                    time.sleep(args.sample_interval)

                distance_mm, ok = window.get_filtered_value()
                if not ok or distance_mm is None:
                    raise RuntimeError(f"no valid ultrasonic sample collected; last error: {last_error}")

                stats = window.stats()
                payload = build_payload(
                    device_id=args.device_id,
                    distance_mm=distance_mm,
                    threshold_mm=args.threshold_mm,
                    stats=stats,
                    source=source,
                )
                result = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
                result.wait_for_publish(timeout=10)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    raise RuntimeError(f"MQTT publish failed with rc={result.rc}")

                published += 1
                marker = " high_water" if payload.get("high_water") else ""
                print(f"published #{published}: {distance_mm}mm samples={stats.count}{marker}")

                elapsed = time.time() - cycle_start
                if elapsed < args.interval:
                    time.sleep(args.interval - elapsed)
    finally:
        client.loop_stop()
        client.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
