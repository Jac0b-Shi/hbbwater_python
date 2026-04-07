"""Text normalization helpers."""

from __future__ import annotations


def repair_mojibake(value: str | None) -> str | None:
    """Repair common UTF-8 bytes that were decoded as Latin-1/CP1252."""
    if not isinstance(value, str) or not value:
        return value

    for source_encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(source_encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        if repaired != value:
            return repaired

    return value
