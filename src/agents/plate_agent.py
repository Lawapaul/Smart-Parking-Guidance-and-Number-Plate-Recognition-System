"""One-shot plate workflow with a low-resource fallback for demos."""

from __future__ import annotations

from dataclasses import dataclass

from src.utils.data_manager import DataManager
from src.utils.paths import VIDEOS_DIR


DEFAULT_VIDEO_PATH = VIDEOS_DIR / "plate.mp4"


@dataclass
class PlateRunResult:
    """Result from a single plate processing pass."""

    plate_text: str
    source: str
    mode: str


class PlateVisionAgent:
    """Store a lightweight demo plate record without changing core ANPR logic."""

    def __init__(self, manager: DataManager) -> None:
        self.manager = manager

    def run_demo_stub(self) -> PlateRunResult:
        """Insert a clearly marked demo vehicle record for low-resource runs."""
        self.manager.add_vehicle(
            plate_text="DEMO-001",
            vehicle_x1=120,
            vehicle_y1=90,
            vehicle_x2=420,
            vehicle_y2=260,
            plate_x1=220,
            plate_y1=180,
            plate_x2=330,
            plate_y2=220,
        )
        return PlateRunResult(
            plate_text="DEMO-001",
            source=str(DEFAULT_VIDEO_PATH),
            mode="stub",
        )
