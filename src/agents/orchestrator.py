"""High-level pipeline orchestration."""

from __future__ import annotations

from src.agents.parking_agent import ParkingVisionAgent
from src.agents.plate_agent import PlateVisionAgent
from src.fusion.risk_fusion import build_runtime_snapshot
from src.utils.config import load_config
from src.utils.data_manager import get_manager, init_db


def run_demo_pipeline() -> dict:
    """Run a lightweight end-to-end repository demo."""
    config = load_config()
    init_db()
    manager = get_manager()

    parking_agent = ParkingVisionAgent(manager)
    parking_agent.run_once()

    if config["demo"].get("use_stub_vehicle", True):
        plate_agent = PlateVisionAgent(manager)
        plate_agent.run_demo_stub()

    slot_counts = manager.get_slot_counts()
    recommendation = manager.get_recommended_slot()
    latest_vehicle = manager.get_latest_vehicle()
    return build_runtime_snapshot(slot_counts, recommendation, latest_vehicle)
