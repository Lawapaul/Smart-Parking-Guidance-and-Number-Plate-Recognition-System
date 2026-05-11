"""Configuration loading helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.utils.paths import CONFIGS_DIR


DEFAULT_CONFIG_PATH = CONFIGS_DIR / "pipeline.json"


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load the project configuration file."""
    target = config_path or DEFAULT_CONFIG_PATH
    with target.open("r", encoding="utf-8") as handle:
        return json.load(handle)
