"""SQLAlchemy ORM entities."""

from sqlalchemy import Boolean, Column, DateTime, Integer, LargeBinary, String
from sqlalchemy.sql import func

from src.models.database import Base


class ParkingSlot(Base):
    """Persisted state for a single parking slot."""

    __tablename__ = "parking_slots"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, unique=True, index=True)
    x = Column(Integer)
    y = Column(Integer)
    w = Column(Integer)
    h = Column(Integer)
    is_occupied = Column(Boolean, default=False)
    slot_mask = Column(LargeBinary, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Vehicle(Base):
    """Persisted state for the latest recognized vehicles."""

    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_text = Column(String, index=True)
    vehicle_x1 = Column(Integer)
    vehicle_y1 = Column(Integer)
    vehicle_x2 = Column(Integer)
    vehicle_y2 = Column(Integer)
    plate_x1 = Column(Integer, nullable=True)
    plate_y1 = Column(Integer, nullable=True)
    plate_x2 = Column(Integer, nullable=True)
    plate_y2 = Column(Integer, nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
