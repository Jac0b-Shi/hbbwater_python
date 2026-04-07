#!/usr/bin/env python3
"""Send test payloads to an immersion sensor webhook endpoint.

Examples:
    python tools/send_immersion_webhook.py http://localhost/api/sensors/webhook/8b69faff1697440f
    python tools/send_immersion_webhook.py http://localhost/api/sensors/webhook/8b69faff1697440f --detected --duration 300 --severity high --status danger
    python tools/send_immersion_webhook.py http://localhost/api/sensors/webhook/8b69faff1697440f --scenario leak
    python tools/send_immersion_webhook.py http://localhost/api/sensors/webhook/8b69faff1697440f --count 12 --interval 2
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error, request


DEFAULT_TIMEOUT = 10


def isoformat_utc(dt: datetime) -> str:
    """Return an ISO timestamp with trailing Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def post_json(url: str, payload: dict[str, Any], timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """POST JSON data using the Python standard library."""
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
            return {
                "ok": True,
                "status": resp.status,
                "body": json.loads(content) if content else {},
            }
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body_data: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body_data = raw
        return {
            "ok": False,
            "status": exc.code,
            "body": body_data,
        }
    except error.URLError as exc:
        return {
            "ok": False,
            "status": None,
            "body": str(exc.reason),
        }


def build_payload(
    *,
    water_detected: bool,
    duration: int,
    severity: str,
    status: str,
    battery_level: float | None,
    external_powered: bool,
    signal_strength: int | None,
    timestamp: datetime | None,
) -> dict[str, Any]:
    """Build a webhook payload accepted by the immersion sensor endpoint."""
    payload: dict[str, Any] = {
        "water_detected": water_detected,
        "duration": duration,
        "severity": severity,
        "status": status,
        "external_powered": external_powered,
    }

    if battery_level is not None:
        payload["battery_level"] = battery_level
    if signal_strength is not None:
        payload["signal_strength"] = signal_strength
    if timestamp is not None:
        payload["timestamp"] = isoformat_utc(timestamp)

    return payload


def random_payload() -> dict[str, Any]:
    """Generate a realistic random immersion reading."""
    rand = random.random()
    if rand < 0.7:
        water_detected = False
        duration = 0
        severity = "low"
        status = "normal"
    elif rand < 0.9:
        water_detected = True
        duration = random.randint(10, 300)
        severity = random.choice(["low", "medium"])
        status = "warning"
    else:
        water_detected = True
        duration = random.randint(300, 3600)
        severity = random.choice(["medium", "high"])
        status = random.choice(["danger", "alarm"])

    return build_payload(
        water_detected=water_detected,
        duration=duration,
        severity=severity,
        status=status,
        battery_level=round(random.uniform(60, 100), 1),
        external_powered=False,
        signal_strength=random.randint(-85, -50),
        timestamp=datetime.now(timezone.utc),
    )


SCENARIOS: dict[str, list[dict[str, Any]]] = {
    "normal": [
        {"water_detected": False, "duration": 0, "severity": "low", "status": "normal"},
        {"water_detected": False, "duration": 0, "severity": "low", "status": "normal"},
        {"water_detected": False, "duration": 0, "severity": "low", "status": "normal"},
    ],
    "leak": [
        {"water_detected": False, "duration": 0, "severity": "low", "status": "normal"},
        {"water_detected": True, "duration": 60, "severity": "low", "status": "warning"},
        {"water_detected": True, "duration": 180, "severity": "medium", "status": "warning"},
        {"water_detected": False, "duration": 0, "severity": "low", "status": "normal"},
    ],
    "flood": [
        {"water_detected": False, "duration": 0, "severity": "low", "status": "normal"},
        {"water_detected": True, "duration": 120, "severity": "medium", "status": "warning"},
        {"water_detected": True, "duration": 600, "severity": "high", "status": "danger"},
        {"water_detected": True, "duration": 1800, "severity": "high", "status": "alarm"},
        {"water_detected": True, "duration": 2400, "severity": "medium", "status": "warning"},
    ],
}


def send_once(url: str, payload: dict[str, Any], timeout: int) -> int:
    """Send a single payload and print the result."""
    result = post_json(url, payload, timeout=timeout)
    print(json.dumps({"payload": payload, "result": result}, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def send_sequence(url: str, sequence: list[dict[str, Any]], timeout: int, interval: float) -> int:
    """Send a sequence of payloads."""
    failed = 0
    for index, item in enumerate(sequence, start=1):
        result = post_json(url, item, timeout=timeout)
        marker = "OK" if result["ok"] else "FAIL"
        print(f"[{index}/{len(sequence)}] {marker} status={result['status']} payload={json.dumps(item, ensure_ascii=False)}")
        if not result["ok"]:
            print(json.dumps(result["body"], ensure_ascii=False, indent=2) if isinstance(result["body"], (dict, list)) else result["body"])
            failed += 1
        if index < len(sequence) and interval > 0:
            time.sleep(interval)
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="向浸水传感器 webhook 地址发送测试数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("webhook_url", help="完整 webhook URL，例如 http://localhost/api/sensors/webhook/<token>")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="请求超时秒数，默认 10")

    parser.add_argument("--detected", action="store_true", help="单条发送时标记为检测到浸水")
    parser.add_argument("--duration", type=int, default=0, help="浸水持续时间，单位秒")
    parser.add_argument("--severity", choices=["low", "medium", "high"], default="low", help="严重程度")
    parser.add_argument("--status", choices=["normal", "warning", "danger", "alarm", "offline"], default="normal", help="状态")
    parser.add_argument("--battery", type=float, help="电池电量")
    parser.add_argument("--external-powered", action="store_true", help="标记为外接有线供电")
    parser.add_argument("--signal", type=int, help="信号强度")

    parser.add_argument("--count", type=int, default=1, help="随机发送条数，默认 1")
    parser.add_argument("--interval", type=float, default=1.0, help="多条发送时间隔秒数，默认 1")
    parser.add_argument("--random", action="store_true", help="发送随机 payload")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), help="发送预设场景序列")
    parser.add_argument("--history-minutes", type=int, default=0, help="按分钟回放历史时间戳，多条发送时从过去开始均匀分布")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count 必须大于等于 1")

    if args.scenario:
        now = datetime.now(timezone.utc)
        sequence = []
        total = len(SCENARIOS[args.scenario])
        for index, item in enumerate(SCENARIOS[args.scenario]):
            timestamp = now - timedelta(minutes=(total - index))
            sequence.append(
                build_payload(
                    water_detected=item["water_detected"],
                    duration=item["duration"],
                    severity=item["severity"],
                    status=item["status"],
                    battery_level=round(random.uniform(70, 95), 1),
                    external_powered=False,
                    signal_strength=random.randint(-80, -60),
                    timestamp=timestamp,
                )
            )
        return send_sequence(args.webhook_url, sequence, args.timeout, args.interval)

    if args.random or args.count > 1:
        base_time = datetime.now(timezone.utc) - timedelta(minutes=max(args.history_minutes, 0))
        sequence = []
        for index in range(args.count):
            payload = random_payload()
            if args.history_minutes > 0 and args.count > 1:
                offset_seconds = (args.history_minutes * 60 / max(args.count - 1, 1)) * index
                payload["timestamp"] = isoformat_utc(base_time + timedelta(seconds=offset_seconds))
            sequence.append(payload)
        return send_sequence(args.webhook_url, sequence, args.timeout, args.interval)

    payload = build_payload(
        water_detected=args.detected,
        duration=args.duration,
        severity=args.severity,
        status=args.status,
        battery_level=args.battery,
        external_powered=args.external_powered,
        signal_strength=args.signal,
        timestamp=datetime.now(timezone.utc),
    )
    return send_once(args.webhook_url, payload, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
