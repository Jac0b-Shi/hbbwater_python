"""Pure Python threshold and status evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusDecision:
    status: str
    alert_type: str | None
    severity: str | None
    message: str | None


def _crossed(value: float, threshold: float | None, direction: str) -> bool:
    if threshold is None:
        return False
    if direction == "less_or_equal":
        return value <= threshold
    return value >= threshold


def evaluate_status(
    *,
    sensor_type: str,
    device_id: str,
    value: float,
    unit: str,
    threshold_warn: float | None,
    threshold_danger: float | None,
    threshold_dir: str,
) -> StatusDecision:
    if sensor_type == "immersion":
        if value >= 1:
            return StatusDecision(
                status="alarm",
                alert_type="water_detected",
                severity="critical",
                message=f"{device_id} 检测到浸水",
            )
        return StatusDecision(status="normal", alert_type=None, severity=None, message=None)

    if _crossed(value, threshold_danger, threshold_dir):
        return StatusDecision(
            status="danger",
            alert_type="high_water",
            severity="high",
            message=f"{device_id} 水位 {value:.2f}{unit} 已触发危险阈值",
        )
    if _crossed(value, threshold_warn, threshold_dir):
        return StatusDecision(
            status="warning",
            alert_type="high_water",
            severity="medium",
            message=f"{device_id} 水位 {value:.2f}{unit} 已触发预警阈值",
        )
    return StatusDecision(status="normal", alert_type=None, severity=None, message=None)

