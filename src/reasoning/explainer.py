"""Generate concise explanations for demo outputs."""

from __future__ import annotations

from typing import Any


def explain_snapshot(snapshot: dict[str, Any]) -> str:
    """Convert a runtime snapshot into a short, beginner-friendly summary."""
    parking = snapshot["parking"]
    recommendation = snapshot.get("recommendation")
    latest_vehicle = snapshot.get("latest_vehicle")

    lines = [
        f"Detected {parking['total']} parking slots.",
        f"{parking['available']} slots are available and {parking['occupied']} are occupied.",
    ]

    if recommendation:
        lines.append(f"Recommended slot: {recommendation['slot']['label']}.")
    else:
        lines.append("No slot recommendation is available yet.")

    if latest_vehicle:
        lines.append(f"Latest recognized vehicle plate: {latest_vehicle['plate_text']}.")
    else:
        lines.append("No vehicle plate has been stored for this run.")

    return " ".join(lines)
