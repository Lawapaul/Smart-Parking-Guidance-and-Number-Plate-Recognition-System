"""Thread-safe data manager for parking and vehicle data"""
from threading import Lock
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from database import SessionLocal
from models import ParkingSlot, Vehicle


class DataManager:
    """Thread-safe manager for accessing parking and vehicle data"""

    def __init__(self):
        self._lock = Lock()

    def get_all_slots(self) -> List[Dict]:
        """Get all parking slots"""
        with self._lock:
            db = SessionLocal()
            try:
                slots = db.query(ParkingSlot).all()
                return [self._slot_to_dict(slot) for slot in slots]
            finally:
                db.close()

    def get_available_slots(self) -> List[Dict]:
        """Get available (empty) parking slots"""
        with self._lock:
            db = SessionLocal()
            try:
                slots = db.query(ParkingSlot).filter(ParkingSlot.is_occupied == False).all()
                return [self._slot_to_dict(slot) for slot in slots]
            finally:
                db.close()

    def get_slot_by_label(self, label: str) -> Optional[Dict]:
        """Get specific slot by label"""
        with self._lock:
            db = SessionLocal()
            try:
                slot = db.query(ParkingSlot).filter(ParkingSlot.label == label).first()
                return self._slot_to_dict(slot) if slot else None
            finally:
                db.close()

    def update_slot_status(self, label: str, is_occupied: bool) -> bool:
        """Update parking slot occupancy status"""
        with self._lock:
            db = SessionLocal()
            try:
                slot = db.query(ParkingSlot).filter(ParkingSlot.label == label).first()
                if slot:
                    slot.is_occupied = is_occupied
                    db.commit()
                    return True
                return False
            except Exception as e:
                print(f"Error updating slot {label}: {e}")
                db.rollback()
                return False
            finally:
                db.close()

    def create_or_update_slot(self, label: str, x: int, y: int, w: int, h: int,
                             is_occupied: bool, slot_mask: Optional[bytes] = None) -> bool:
        """Create or update a parking slot"""
        with self._lock:
            db = SessionLocal()
            try:
                slot = db.query(ParkingSlot).filter(ParkingSlot.label == label).first()
                if slot:
                    slot.x = x
                    slot.y = y
                    slot.w = w
                    slot.h = h
                    slot.is_occupied = is_occupied
                    if slot_mask:
                        slot.slot_mask = slot_mask
                else:
                    slot = ParkingSlot(
                        label=label,
                        x=x,
                        y=y,
                        w=w,
                        h=h,
                        is_occupied=is_occupied,
                        slot_mask=slot_mask
                    )
                    db.add(slot)
                db.commit()
                return True
            except Exception as e:
                print(f"Error creating/updating slot {label}: {e}")
                db.rollback()
                return False
            finally:
                db.close()

    def bulk_upsert_slots(self, slots: List[Dict]) -> bool:
        """Create or update many parking slots in one transaction."""
        with self._lock:
            db = SessionLocal()
            try:
                for slot_data in slots:
                    label = slot_data["label"]
                    slot = db.query(ParkingSlot).filter(ParkingSlot.label == label).first()
                    if slot:
                        slot.x = slot_data["x"]
                        slot.y = slot_data["y"]
                        slot.w = slot_data["w"]
                        slot.h = slot_data["h"]
                        slot.is_occupied = slot_data["is_occupied"]
                    else:
                        slot = ParkingSlot(**slot_data)
                        db.add(slot)
                db.commit()
                return True
            except Exception as e:
                print(f"Error bulk upserting slots: {e}")
                db.rollback()
                return False
            finally:
                db.close()

    def get_vehicles(self, limit: int = 50) -> List[Dict]:
        """Get recently detected vehicles"""
        with self._lock:
            db = SessionLocal()
            try:
                vehicles = db.query(Vehicle).order_by(Vehicle.detected_at.desc()).limit(limit).all()
                return [self._vehicle_to_dict(v) for v in vehicles]
            finally:
                db.close()

    def add_vehicle(self, plate_text: str, vehicle_x1: int, vehicle_y1: int,
                   vehicle_x2: int, vehicle_y2: int,
                   plate_x1: Optional[int] = None, plate_y1: Optional[int] = None,
                   plate_x2: Optional[int] = None, plate_y2: Optional[int] = None) -> bool:
        """Add a detected vehicle"""
        with self._lock:
            db = SessionLocal()
            try:
                latest_vehicle = (
                    db.query(Vehicle)
                    .filter(Vehicle.plate_text == plate_text)
                    .order_by(Vehicle.detected_at.desc())
                    .first()
                )
                if (
                    latest_vehicle
                    and latest_vehicle.detected_at
                    and latest_vehicle.detected_at >= datetime.utcnow() - timedelta(seconds=20)
                ):
                    return True

                vehicle = Vehicle(
                    plate_text=plate_text,
                    vehicle_x1=vehicle_x1,
                    vehicle_y1=vehicle_y1,
                    vehicle_x2=vehicle_x2,
                    vehicle_y2=vehicle_y2,
                    plate_x1=plate_x1,
                    plate_y1=plate_y1,
                    plate_x2=plate_x2,
                    plate_y2=plate_y2
                )
                db.add(vehicle)
                db.commit()
                return True
            except Exception as e:
                print(f"Error adding vehicle: {e}")
                db.rollback()
                return False
            finally:
                db.close()

    def get_latest_vehicle(self) -> Optional[Dict]:
        """Get the most recent detected vehicle."""
        with self._lock:
            db = SessionLocal()
            try:
                vehicle = db.query(Vehicle).order_by(Vehicle.detected_at.desc()).first()
                return self._vehicle_to_dict(vehicle) if vehicle else None
            finally:
                db.close()

    def get_recommended_slot(self) -> Optional[Dict]:
        """Choose the nearest available slot from the entrance."""
        available_slots = self.get_available_slots()
        if not available_slots:
            return None

        max_x = max(slot["x"] + slot["w"] for slot in available_slots)
        max_y = max(slot["y"] + slot["h"] for slot in available_slots)
        entrance = {
            "x": max_x // 2,
            "y": max_y + 40,
        }

        def score(slot: Dict) -> tuple[float, int, int]:
            center_x = slot["x"] + slot["w"] / 2
            center_y = slot["y"] + slot["h"] / 2
            manhattan = abs(center_x - entrance["x"]) + abs(center_y - entrance["y"])
            return (manhattan, slot["y"], slot["x"])

        best_slot = min(available_slots, key=score)
        return {
            "slot": best_slot,
            "entrance": entrance,
            "directions": self._build_directions(best_slot, entrance),
        }

    def get_slot_counts(self) -> Dict[str, int]:
        """Get counts of total, available, and occupied slots"""
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
                    "efficiency": round((occupied / total * 100) if total > 0 else 0, 2)
                }
            finally:
                db.close()

    # Helper methods
    @staticmethod
    def _slot_to_dict(slot: ParkingSlot) -> Dict:
        """Convert ParkingSlot ORM to dict"""
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
            "updated_at": slot.updated_at.isoformat() if slot.updated_at else None
        }

    @staticmethod
    def _vehicle_to_dict(vehicle: Vehicle) -> Dict:
        """Convert Vehicle ORM to dict"""
        if not vehicle:
            return None
        return {
            "id": vehicle.id,
            "plate_text": vehicle.plate_text,
            "vehicle_bbox": [vehicle.vehicle_x1, vehicle.vehicle_y1, vehicle.vehicle_x2, vehicle.vehicle_y2],
            "plate_bbox": [vehicle.plate_x1, vehicle.plate_y1, vehicle.plate_x2, vehicle.plate_y2] if vehicle.plate_x1 else None,
            "detected_at": vehicle.detected_at.isoformat() if vehicle.detected_at else None
        }

    @staticmethod
    def _build_directions(slot: Dict, entrance: Dict[str, int]) -> Dict:
        """Create lightweight turn-by-turn directions from the entrance to a slot."""
        target_x = slot["x"] + slot["w"] // 2
        target_y = slot["y"] + slot["h"] // 2
        horizontal_delta = target_x - entrance["x"]
        horizontal_direction = "right" if horizontal_delta >= 0 else "left"

        steps = [
            f"Enter from the bottom center of the parking layout.",
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


# Global instance
_manager = DataManager()


def get_manager() -> DataManager:
    """Get the global DataManager instance"""
    return _manager
