"""Parking-related API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.utils.data_manager import get_manager
from src.utils.paths import MASKS_DIR


router = APIRouter(prefix="/parking", tags=["parking"])


class ParkingSlotIngest(BaseModel):
    """Incoming parking slot payload."""

    label: str
    x: int
    y: int
    w: int
    h: int
    is_occupied: bool


class ParkingSlotsIngestRequest(BaseModel):
    """Parking slot ingest request."""

    slots: list[ParkingSlotIngest]


class VehicleIngestRequest(BaseModel):
    """Vehicle ingest request."""

    plate_text: str
    vehicle_bbox: list[int]
    plate_bbox: list[int] | None = None


@router.get("/slots")
async def get_all_slots() -> dict[str, Any]:
    """Return all parking slots and aggregate counts."""
    manager = get_manager()
    counts = manager.get_slot_counts()
    return {
        **counts,
        "slots": manager.get_all_slots(),
    }


@router.get("/slots/available")
async def get_available_slots() -> dict[str, Any]:
    """Return only available parking slots."""
    manager = get_manager()
    slots = manager.get_available_slots()
    return {
        "count": len(slots),
        "nearest_pillar": slots[0]["label"] if slots else None,
        "slots": slots,
    }


@router.get("/slots/recommendation")
async def get_recommended_slot() -> dict[str, Any]:
    """Return the best available slot."""
    manager = get_manager()
    return {
        "recommendation": manager.get_recommended_slot(),
        "latest_vehicle": manager.get_latest_vehicle(),
    }


@router.get("/vehicles")
async def get_detected_vehicles(limit: int = 50) -> dict[str, Any]:
    """Return recent detected vehicles."""
    manager = get_manager()
    vehicles = manager.get_vehicles(limit=limit)
    return {"count": len(vehicles), "vehicles": vehicles}


@router.get("/stats")
async def get_parking_stats() -> dict[str, Any]:
    """Return parking statistics."""
    return get_manager().get_slot_counts()


@router.get("/mask-info")
async def get_mask_info() -> dict[str, Any]:
    """Return mask dimensions for the dashboard."""
    for candidate in (MASKS_DIR / "mask.png", MASKS_DIR / "mask_crop.png"):
        if candidate.exists():
            mask = cv2.imread(str(candidate), cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                height, width = mask.shape
                return {"width": width, "height": height, "has_mask": True}
    return {"width": 0, "height": 0, "has_mask": False}


@router.post("/ingest/slots")
async def ingest_slots(payload: ParkingSlotsIngestRequest) -> dict[str, Any]:
    """Accept parking slot state updates from the CV runtime."""
    manager = get_manager()
    if not manager.bulk_upsert_slots([slot.model_dump() for slot in payload.slots]):
        raise HTTPException(status_code=500, detail="Failed to store slot data")
    return {
        "stored": len(payload.slots),
        "counts": manager.get_slot_counts(),
        "recommendation": manager.get_recommended_slot(),
    }


@router.post("/ingest/vehicle")
async def ingest_vehicle(payload: VehicleIngestRequest) -> dict[str, Any]:
    """Accept vehicle and plate updates from the CV runtime."""
    if len(payload.vehicle_bbox) != 4:
        raise HTTPException(status_code=400, detail="vehicle_bbox must have 4 integers")

    plate_bbox = payload.plate_bbox if payload.plate_bbox and len(payload.plate_bbox) == 4 else [None] * 4
    manager = get_manager()
    if not manager.add_vehicle(
        plate_text=payload.plate_text,
        vehicle_x1=payload.vehicle_bbox[0],
        vehicle_y1=payload.vehicle_bbox[1],
        vehicle_x2=payload.vehicle_bbox[2],
        vehicle_y2=payload.vehicle_bbox[3],
        plate_x1=plate_bbox[0],
        plate_y1=plate_bbox[1],
        plate_x2=plate_bbox[2],
        plate_y2=plate_bbox[3],
    ):
        raise HTTPException(status_code=500, detail="Failed to store vehicle data")
    return {"stored": True, "recommendation": manager.get_recommended_slot()}
