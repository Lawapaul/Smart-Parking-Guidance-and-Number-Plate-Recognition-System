"""Thread-safe data access layer for parking and vehicle state."""

from __future__ import annotations

from datetime import datetime, timedelta
from threading import Lock
from typing import Any

from src.decision.planner import recommend_slot
from src.models.database import Base, SessionLocal, engine
from src.models.entities import ParkingSlot, Vehicle


def init_db() -> None:
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


class DataManager:
    """Coordinate storage and retrieval for parking slots and vehicles."""

    def __init__(self) -> None:
        self._lock = Lock()

    def get_all_slots(self) -> list[dict[str, Any]]:
        """Return all parking slots."""
        with self._lock:
            db = SessionLocal()
            try:
                slots = db.query(ParkingSlot).all()
                return [self._slot_to_dict(slot) for slot in slots]
            finally:
                db.close()

    def get_available_slots(self) -> list[dict[str, Any]]:
        """Return only available parking slots."""
        with self._lock:
            db = SessionLocal()
            try:
                slots = db.query(ParkingSlot).filter(ParkingSlot.is_occupied == False).all()
                return [self._slot_to_dict(slot) for slot in slots]
            finally:
                db.close()

    def bulk_upsert_slots(self, slots: list[dict[str, Any]]) -> bool:
        """Create or update many parking slots in one transaction."""
        with self._lock:
            db = SessionLocal()
            try:
                for slot_data in slots:
                    slot = db.query(ParkingSlot).filter(ParkingSlot.label == slot_data["label"]).first()
                    if slot:
                        slot.x = slot_data["x"]
                        slot.y = slot_data["y"]
                        slot.w = slot_data["w"]
                        slot.h = slot_data["h"]
                        slot.is_occupied = slot_data["is_occupied"]
                    else:
                        db.add(ParkingSlot(**slot_data))
                db.commit()
                return True
            except Exception:
                db.rollback()
                return False
            finally:
                db.close()

    def add_vehicle(
        self,
        plate_text: str,
        vehicle_x1: int,
        vehicle_y1: int,
        vehicle_x2: int,
        vehicle_y2: int,
        plate_x1: int | None = None,
        plate_y1: int | None = None,
        plate_x2: int | None = None,
        plate_y2: int | None = None,
    ) -> bool:
        """Add a detected vehicle unless it is a very recent duplicate."""
        with self._lock:
            db = SessionLocal()
            try:
                latest_vehicle = (
                    db.query(Vehicle)
                    .filter(Vehicle.plate_text == plate_text)
                    .order_by(Vehicle.detected_at.desc())
                    .first()
                )
                if latest_vehicle and latest_vehicle.detected_at:
                    if latest_vehicle.detected_at >= datetime.utcnow() - timedelta(seconds=20):
                        return True

                db.add(
                    Vehicle(
                        plate_text=plate_text,
                        vehicle_x1=vehicle_x1,
                        vehicle_y1=vehicle_y1,
                        vehicle_x2=vehicle_x2,
                        vehicle_y2=vehicle_y2,
                        plate_x1=plate_x1,
                        plate_y1=plate_y1,
                        plate_x2=plate_x2,
                        plate_y2=plate_y2,
                    )
                )
                db.commit()
                return True
            except Exception:
                db.rollback()
                return False
            finally:
                db.close()

    def get_latest_vehicle(self) -> dict[str, Any] | None:
        """Return the latest stored vehicle."""
        with self._lock:
            db = SessionLocal()
            try:
                vehicle = db.query(Vehicle).order_by(Vehicle.detected_at.desc()).first()
                return self._vehicle_to_dict(vehicle) if vehicle else None
            finally:
                db.close()

    def get_vehicles(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recently detected vehicles."""
        with self._lock:
            db = SessionLocal()
            try:
                vehicles = db.query(Vehicle).order_by(Vehicle.detected_at.desc()).limit(limit).all()
                return [self._vehicle_to_dict(vehicle) for vehicle in vehicles]
            finally:
                db.close()

    def get_slot_counts(self) -> dict[str, Any]:
        """Return parking slot statistics."""
        with self._lock:
            db = SessionLocal()
            try:
                total = db.query(ParkingSlot).count()
                available = db.query(ParkingSlot).filter(ParkingSlot.is_occupied == False).count()
                occupied = total - available
                return {
                    "total": total,
                    "available": available,
                    "occupied": occupied,
                    "efficiency": round((occupied / total * 100) if total else 0, 2),
                }
            finally:
                db.close()

    def get_recommended_slot(self) -> dict[str, Any] | None:
        """Return the current best available slot."""
        return recommend_slot(self.get_available_slots())

    @staticmethod
    def _slot_to_dict(slot: ParkingSlot) -> dict[str, Any] | None:
        """Serialize a parking slot ORM instance."""
        if not slot:
            return None
        return {
            "id": slot.id,
            "label": slot.label,
            "x": slot.x,
            "y": slot.y,
            "w": slot.w,
            "h": slot.h,
            "is_occupied": slot.is_occupied,
            "updated_at": slot.updated_at.isoformat() if slot.updated_at else None,
        }

    @staticmethod
    def _vehicle_to_dict(vehicle: Vehicle) -> dict[str, Any] | None:
        """Serialize a vehicle ORM instance."""
        if not vehicle:
            return None
        return {
            "id": vehicle.id,
            "plate_text": vehicle.plate_text,
            "vehicle_bbox": [vehicle.vehicle_x1, vehicle.vehicle_y1, vehicle.vehicle_x2, vehicle.vehicle_y2],
            "plate_bbox": [vehicle.plate_x1, vehicle.plate_y1, vehicle.plate_x2, vehicle.plate_y2]
            if vehicle.plate_x1 is not None
            else None,
            "detected_at": vehicle.detected_at.isoformat() if vehicle.detected_at else None,
        }


_manager = DataManager()


def get_manager() -> DataManager:
    """Return the shared data manager."""
    return _manager
