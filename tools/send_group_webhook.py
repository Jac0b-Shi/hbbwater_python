#!/usr/bin/env python3
"""Send test payloads to a webhook group endpoint.

Examples:
    python tools/send_group_webhook.py --list-groups
    python tools/send_group_webhook.py --group-name a
    python tools/send_group_webhook.py --group-name b --device-imei 000000000000002 --water-status 1
    python tools/send_group_webhook.py --sensor-type ultrasonic --measurement-value 128.4
    python tools/send_group_webhook.py http://localhost/api/sensors/group-webhook/91cfe2ee2ec3a9a8 --sensor-type ultrasonic --device-imei 000000000000000
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error, parse, request


DEFAULT_API_BASE = "http://localhost:8000"
DEFAULT_TIMEOUT = 10


def isoformat_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT) -> Any:
    with request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return {"ok": True, "status": resp.status, "body": json.loads(content) if content else {}}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body_data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body_data = raw
        return {"ok": False, "status": exc.code, "body": body_data}
    except error.URLError as exc:
        return {"ok": False, "status": None, "body": str(exc.reason)}


def normalize_api_base(api_base: str) -> str:
    return api_base.rstrip("/")


def normalize_group_url(api_base: str, token: str) -> str:
    return f"{normalize_api_base(api_base)}/api/sensors/group-webhook/{token}"


def extract_token_from_target(target: str) -> str:
    parsed = parse.urlparse(target)
    if parsed.scheme and parsed.netloc:
        return parsed.path.rstrip("/").split("/")[-1]
    return target.strip()


def load_groups(api_base: str, timeout: int) -> list[dict[str, Any]]:
    return fetch_json(f"{normalize_api_base(api_base)}/api/sensors/groups", timeout=timeout)


def select_group(
    groups: list[dict[str, Any]],
    *,
    group_name: str | None,
    group_id: int | None,
    group_token: str | None,
    sensor_type: str | None,
) -> dict[str, Any]:
    candidates = groups
    if group_id is not None:
        candidates = [group for group in candidates if group["id"] == group_id]
    if group_name:
        candidates = [group for group in candidates if group["name"] == group_name]
    if group_token:
        candidates = [group for group in candidates if group["webhook_token"] == group_token]
    if sensor_type:
        candidates = [
            group
            for group in candidates
            if group["sensors"] and all(sensor["sensor_type"] == sensor_type for sensor in group["sensors"])
        ]
    if not candidates:
        raise ValueError("No matching webhook group found")
    return candidates[0]


def select_sensor(group: dict[str, Any], device_imei: str | None) -> dict[str, Any]:
    sensors = group.get("sensors") or []
    if not sensors:
        raise ValueError("The selected group has no sensors")
    if device_imei:
        for sensor in sensors:
            if sensor.get("device_imei") == device_imei:
                return sensor
        raise ValueError(f"Device IMEI {device_imei} is not bound in group {group['name']}")
    return sensors[0]


def build_immersion_payload(
    *,
    device_imei: str,
    detected: bool,
    water_status: int | None,
    status: str | None,
    timestamp: datetime,
) -> dict[str, Any]:
    resolved_water_status = water_status if water_status is not None else int(detected)
    return {
        "device_imei": device_imei,
        "sensor_type": "immersion",
        "msg_type": 1,
        "msg_type_name": "状态变化",
        "water_status": resolved_water_status,
        "water_status_text": "有水" if resolved_water_status else "无水",
        "water_detected": bool(resolved_water_status),
        "raw_hex": f"{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}",
        "timestamp": isoformat_utc(timestamp),
        **({"status": status} if status else {}),
    }


def build_ultrasonic_payload(
    *,
    device_imei: str,
    measurement_value: float | None,
    adc_raw: int | None,
    status: str | None,
    timestamp: datetime,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "device_imei": device_imei,
        "sensor_type": "ultrasonic",
        "msg_type": 1,
        "msg_type_name": "状态变化",
        "raw_hex": "uart-packet-hex",
        "timestamp": isoformat_utc(timestamp),
    }
    if measurement_value is not None:
        payload["measurement_value"] = measurement_value
    if adc_raw is not None:
        payload["adc_raw"] = adc_raw
    if status:
        payload["status"] = status
    if measurement_value is None and adc_raw is None:
        payload["measurement_value"] = round(random.uniform(5, 150), 1)
    return payload


def build_payload(
    *,
    sensor_type: str,
    device_imei: str,
    detected: bool,
    water_status: int | None,
    measurement_value: float | None,
    adc_raw: int | None,
    status: str | None,
    timestamp: datetime,
) -> dict[str, Any]:
    if sensor_type == "immersion":
        return build_immersion_payload(
            device_imei=device_imei,
            detected=detected,
            water_status=water_status,
            status=status,
            timestamp=timestamp,
        )
    return build_ultrasonic_payload(
        device_imei=device_imei,
        measurement_value=measurement_value,
        adc_raw=adc_raw,
        status=status,
        timestamp=timestamp,
    )


def send_sequence(
    url: str,
    payloads: list[dict[str, Any]],
    timeout: int,
    interval: float,
) -> int:
    failures = 0
    for index, payload in enumerate(payloads, start=1):
        result = post_json(url, payload, timeout=timeout)
        marker = "OK" if result["ok"] else "FAIL"
        print(f"[{index}/{len(payloads)}] {marker} status={result['status']} payload={json.dumps(payload, ensure_ascii=False)}")
        if not result["ok"]:
            failures += 1
            print(json.dumps(result["body"], ensure_ascii=False, indent=2) if isinstance(result["body"], (dict, list)) else result["body"])
        if index < len(payloads) and interval > 0:
            time.sleep(interval)
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="向组 webhook 地址发送测试数据")
    parser.add_argument("target", nargs="?", help="完整组 webhook URL、组 token，或留空后配合查询参数自动发现")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="API 基础地址，默认 http://localhost:8000")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="请求超时秒数")
    parser.add_argument("--list-groups", action="store_true", help="列出当前已有组并退出")
    parser.add_argument("--group-name", help="按组名称选择")
    parser.add_argument("--group-id", type=int, help="按组ID选择")
    parser.add_argument("--sensor-type", choices=["ultrasonic", "immersion"], help="按组内传感器类型选择")
    parser.add_argument("--device-imei", help="指定组内设备IMEI，默认取该组第一个成员")
    parser.add_argument("--count", type=int, default=1, help="发送条数，默认 1")
    parser.add_argument("--interval", type=float, default=1.0, help="多条发送间隔秒数")
    parser.add_argument("--history-minutes", type=int, default=0, help="历史回放分钟数")
    parser.add_argument("--status", choices=["normal", "warning", "danger", "alarm", "offline"], help="显式覆盖状态")
    parser.add_argument("--detected", action="store_true", help="浸水组单发时标记为有水")
    parser.add_argument("--water-status", type=int, choices=[0, 1], help="浸水组显式指定 water_status")
    parser.add_argument("--measurement-value", type=float, help="超声波组测量值，单位按后台传感器返回单位配置解释")
    parser.add_argument("--adc-raw", type=int, help="作为兜底测量值发送，单位按后台传感器返回单位配置解释")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    groups = load_groups(args.api_base, args.timeout)
    if args.list_groups:
        print(json.dumps(groups, ensure_ascii=False, indent=2))
        return 0

    target_token = extract_token_from_target(args.target) if args.target else None
    group = select_group(
        groups,
        group_name=args.group_name,
        group_id=args.group_id,
        group_token=target_token,
        sensor_type=args.sensor_type,
    )
    sensor = select_sensor(group, args.device_imei)
    resolved_sensor_type = sensor["sensor_type"]
    url = normalize_group_url(args.api_base, group["webhook_token"])

    if args.count < 1:
        parser.error("--count 必须大于等于 1")

    base_time = datetime.now(timezone.utc) - timedelta(minutes=max(args.history_minutes, 0))
    payloads = []
    for index in range(args.count):
        timestamp = base_time
        if args.history_minutes > 0 and args.count > 1:
            offset_seconds = (args.history_minutes * 60 / max(args.count - 1, 1)) * index
            timestamp = base_time + timedelta(seconds=offset_seconds)
        else:
            timestamp = datetime.now(timezone.utc)
        payloads.append(
            build_payload(
                sensor_type=resolved_sensor_type,
                device_imei=sensor["device_imei"],
                detected=args.detected,
                water_status=args.water_status,
                measurement_value=args.measurement_value,
                adc_raw=args.adc_raw,
                status=args.status,
                timestamp=timestamp,
            )
        )

    print(
        json.dumps(
            {
                "group": {"id": group["id"], "name": group["name"], "token": group["webhook_token"]},
                "sensor": {"sensor_id": sensor["sensor_id"], "sensor_type": sensor["sensor_type"], "device_imei": sensor["device_imei"]},
                "webhook_url": url,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return send_sequence(url, payloads, args.timeout, args.interval)


if __name__ == "__main__":
    sys.exit(main())
