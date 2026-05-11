"""Pure decision-planning helpers for parking slot recommendations."""

from __future__ import annotations

from typing import Any


def build_directions(slot: dict[str, Any], entrance: dict[str, int]) -> dict[str, Any]:
    """Create lightweight turn-by-turn directions from the entrance to a slot."""
    target_x = slot["x"] + slot["w"] // 2
    target_y = slot["y"] + slot["h"] // 2
    horizontal_delta = target_x - entrance["x"]
    horizontal_direction = "right" if horizontal_delta >= 0 else "left"

    steps = [
        "Enter from the bottom center of the parking layout.",
        f"Go straight for about {max(0, entrance['y'] - target_y)} pixels.",
    ]

    if horizontal_delta != 0:
        steps.append(f"Turn {horizontal_direction} for about {abs(horizontal_delta)} pixels.")

    steps.append(f"Stop at slot {slot['label']}.")

    return {
        "text": " ".join(steps),
        "steps": steps,
        "path": [
            {"x": entrance["x"], "y": entrance["y"]},
            {"x": entrance["x"], "y": target_y},
            {"x": target_x, "y": target_y},
        ],
    }


def recommend_slot(available_slots: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Choose the nearest available slot from the entrance."""
    if not available_slots:
        return None

    max_x = max(slot["x"] + slot["w"] for slot in available_slots)
    max_y = max(slot["y"] + slot["h"] for slot in available_slots)
    entrance = {"x": max_x // 2, "y": max_y + 40}

    def score(slot: dict[str, Any]) -> tuple[float, int, int]:
        center_x = slot["x"] + slot["w"] / 2
        center_y = slot["y"] + slot["h"] / 2
        manhattan = abs(center_x - entrance["x"]) + abs(center_y - entrance["y"])
        return (manhattan, slot["y"], slot["x"])

    best_slot = min(available_slots, key=score)
    return {
        "slot": best_slot,
        "entrance": entrance,
        "directions": build_directions(best_slot, entrance),
    }
