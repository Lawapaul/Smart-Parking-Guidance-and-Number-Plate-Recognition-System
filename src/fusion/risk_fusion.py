"""Combine parking and vehicle context into a compact runtime summary."""

from __future__ import annotations

from typing import Any


def build_runtime_snapshot(
    slot_counts: dict[str, Any],
    recommendation: dict[str, Any] | None,
    latest_vehicle: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fuse system outputs into one payload for APIs, demos, and reports."""
    return {
        "parking": slot_counts,
        "recommendation": recommendation,
        "latest_vehicle": latest_vehicle,
    }
