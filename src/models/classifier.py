"""Wrappers around the existing parking slot classifier logic."""

from pathlib import Path

from parking import empty_or_not, load_classifier, resolve_model_path


def load_parking_classifier(model_path: Path | None = None):
    """Load the existing parking occupancy classifier."""
    return load_classifier(model_path or resolve_model_path())


def predict_is_occupied(classifier, spot_bgr) -> bool:
    """Predict whether a parking slot is occupied."""
    return not empty_or_not(classifier, spot_bgr)
