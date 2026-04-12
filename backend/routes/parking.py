"""Parking-related API routes"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import cv2
from pathlib import Path

from services.data_manager import get_manager

router = APIRouter(prefix="/parking", tags=["parking"])


# Pydantic models for requests/responses
class ParkingSlotResponse(BaseModel):
    id: int
    label: str
    x: int
    y: int
    w: int
    h: int
    is_occupied: bool
    updated_at: str


class VehicleResponse(BaseModel):
    id: int
    plate_text: str
    vehicle_bbox: List[int]
    plate_bbox: List[int] = None
    detected_at: str


class SlotCountsResponse(BaseModel):
    total: int
    available: int
    occupied: int
    efficiency: float


class MaskInfoResponse(BaseModel):
    width: int
    height: int
    has_mask: bool


class ParkingSlotIngest(BaseModel):
    label: str
    x: int
    y: int
    w: int
    h: int
    is_occupied: bool


class ParkingSlotsIngestRequest(BaseModel):
    slots: List[ParkingSlotIngest]


class VehicleIngestRequest(BaseModel):
    plate_text: str
    vehicle_bbox: List[int]
    plate_bbox: Optional[List[int]] = None


@router.get("/slots", response_model=Dict[str, Any])
async def get_all_slots():
    """Get all parking slots with their status"""
    try:
        manager = get_manager()
        slots = manager.get_all_slots()
        counts = manager.get_slot_counts()

        return {
            "total": counts["total"],
            "available": counts["available"],
            "occupied": counts["occupied"],
            "efficiency": counts["efficiency"],
            "slots": slots
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slots/available", response_model=Dict[str, Any])
async def get_available_slots():
    """Get only available (empty) parking slots"""
    try:
        manager = get_manager()
        slots = manager.get_available_slots()

        return {
            "count": len(slots),
            "nearest_pillar": slots[0]["label"] if slots else None,
            "slots": slots
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slots/recommendation", response_model=Dict[str, Any])
async def get_recommended_slot():
    """Get the best currently available slot and directions to it."""
    try:
        manager = get_manager()
        recommendation = manager.get_recommended_slot()
        latest_vehicle = manager.get_latest_vehicle()

        return {
            "recommendation": recommendation,
            "latest_vehicle": latest_vehicle,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vehicles", response_model=Dict[str, Any])
async def get_detected_vehicles(limit: int = 50):
    """Get recently detected vehicles with license plates"""
    try:
        manager = get_manager()
        vehicles = manager.get_vehicles(limit=limit)

        return {
            "count": len(vehicles),
            "vehicles": vehicles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mask-info", response_model=MaskInfoResponse)
async def get_mask_info():
    """Get mask information for visualization (dimensions, etc)"""
    try:
        # Try to load mask image
        mask_paths = [
            Path(__file__).resolve().parents[2] / "data/masks/mask.png",
            Path(__file__).resolve().parents[2] / "data/masks/mask_crop.png",
        ]

        for mask_path in mask_paths:
            if mask_path.exists():
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if mask is not None:
                    height, width = mask.shape
                    return MaskInfoResponse(
                        width=width,
                        height=height,
                        has_mask=True
                    )

        # No mask found
        return MaskInfoResponse(
            width=0,
            height=0,
            has_mask=False
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=SlotCountsResponse)
async def get_parking_stats():
    """Get parking statistics"""
    try:
        manager = get_manager()
        counts = manager.get_slot_counts()

        return SlotCountsResponse(**counts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        manager = get_manager()
        counts = manager.get_slot_counts()

        return {
            "status": "healthy",
            "total_slots": counts["total"],
            "available_slots": counts["available"]
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.post("/ingest/slots", response_model=Dict[str, Any])
async def ingest_slots(payload: ParkingSlotsIngestRequest):
    """Accept parking slot state updates from the CV runtime."""
    try:
        manager = get_manager()
        success = manager.bulk_upsert_slots([slot.model_dump() for slot in payload.slots])
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store slot data")

        counts = manager.get_slot_counts()
        recommendation = manager.get_recommended_slot()
        return {
            "stored": len(payload.slots),
            "counts": counts,
            "recommendation": recommendation,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/vehicle", response_model=Dict[str, Any])
async def ingest_vehicle(payload: VehicleIngestRequest):
    """Accept vehicle and plate updates from the CV runtime."""
    try:
        if len(payload.vehicle_bbox) != 4:
            raise HTTPException(status_code=400, detail="vehicle_bbox must have 4 integers")

        plate_bbox = payload.plate_bbox if payload.plate_bbox and len(payload.plate_bbox) == 4 else [None] * 4

        manager = get_manager()
        success = manager.add_vehicle(
            plate_text=payload.plate_text,
            vehicle_x1=payload.vehicle_bbox[0],
            vehicle_y1=payload.vehicle_bbox[1],
            vehicle_x2=payload.vehicle_bbox[2],
            vehicle_y2=payload.vehicle_bbox[3],
            plate_x1=plate_bbox[0],
            plate_y1=plate_bbox[1],
            plate_x2=plate_bbox[2],
            plate_y2=plate_bbox[3],
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store vehicle data")

        recommendation = manager.get_recommended_slot()
        return {
            "stored": True,
            "recommendation": recommendation,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
