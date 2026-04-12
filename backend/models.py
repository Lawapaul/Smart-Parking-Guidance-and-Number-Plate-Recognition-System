from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, LargeBinary
from sqlalchemy.sql import func
from database import Base


class ParkingSlot(Base):
    """ORM model for parking slots"""
    __tablename__ = "parking_slots"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, unique=True, index=True)  # e.g., "P1-S1"
    x = Column(Integer)  # X coordinate
    y = Column(Integer)  # Y coordinate
    w = Column(Integer)  # Width
    h = Column(Integer)  # Height
    is_occupied = Column(Boolean, default=False)
    slot_mask = Column(LargeBinary, nullable=True)  # Binary mask data
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Vehicle(Base):
    """ORM model for detected vehicles"""
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_text = Column(String, index=True)  # License plate text
    vehicle_x1 = Column(Integer)  # Vehicle bounding box X1
    vehicle_y1 = Column(Integer)  # Vehicle bounding box Y1
    vehicle_x2 = Column(Integer)  # Vehicle bounding box X2
    vehicle_y2 = Column(Integer)  # Vehicle bounding box Y2
    plate_x1 = Column(Integer, nullable=True)  # Plate bounding box X1
    plate_y1 = Column(Integer, nullable=True)  # Plate bounding box Y1
    plate_x2 = Column(Integer, nullable=True)  # Plate bounding box X2
    plate_y2 = Column(Integer, nullable=True)  # Plate bounding box Y2
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
