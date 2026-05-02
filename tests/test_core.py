"""Core behavior tests that require only the Python business modules."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.payload import parse_sensor_payload
from app.services.status import evaluate_status


class PayloadParsingTests(unittest.TestCase):
    def test_ultrasonic_mqtt_payload_normalizes_mm_to_cm(self) -> None:
        parsed = parse_sensor_payload(
            {"value": 125, "unit": "mm", "battery": 88},
            topic="hbbwater/ultrasonic/US001/data",
        )

        self.assertEqual(parsed.device_id, "US001")
        self.assertEqual(parsed.sensor_type, "ultrasonic")
        self.assertEqual(parsed.value, 12.5)
        self.assertEqual(parsed.unit, "cm")
        self.assertEqual(parsed.battery, 88)

    def test_immersion_payload_converts_boolean_to_state_value(self) -> None:
        parsed = parse_sensor_payload(
            {"device_id": "IM001", "type": "immersion", "water_detected": True},
        )

        self.assertEqual(parsed.value, 1.0)
        self.assertEqual(parsed.unit, "state")


class StatusEvaluationTests(unittest.TestCase):
    def test_ultrasonic_danger_threshold(self) -> None:
        decision = evaluate_status(
            sensor_type="ultrasonic",
            device_id="US001",
            value=21,
            unit="cm",
            threshold_warn=10,
            threshold_danger=20,
            threshold_dir="greater_or_equal",
        )

        self.assertEqual(decision.status, "danger")
        self.assertEqual(decision.alert_type, "high_water")
        self.assertEqual(decision.severity, "high")

    def test_immersion_alarm(self) -> None:
        decision = evaluate_status(
            sensor_type="immersion",
            device_id="IM001",
            value=1,
            unit="state",
            threshold_warn=1,
            threshold_danger=1,
            threshold_dir="greater_or_equal",
        )

        self.assertEqual(decision.status, "alarm")
        self.assertEqual(decision.alert_type, "water_detected")
        self.assertEqual(decision.severity, "critical")


if __name__ == "__main__":
    unittest.main()

