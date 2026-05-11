"""Render demo results for CLI output."""

from __future__ import annotations

from src.reasoning.explainer import explain_snapshot


def render_console_report(snapshot: dict) -> str:
    """Create a compact report for `python main.py`."""
    explanation = explain_snapshot(snapshot)
    recommendation = snapshot.get("recommendation")
    lines = [
        "Smart Parking System Demo",
        "=" * 26,
        explanation,
    ]
    if recommendation:
        lines.append(f"Directions: {recommendation['directions']['text']}")
    return "\n".join(lines)
