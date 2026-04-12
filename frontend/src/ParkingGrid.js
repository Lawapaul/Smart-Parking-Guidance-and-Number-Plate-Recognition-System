import React from 'react';
import './ParkingGrid.css';

function ParkingGrid({ slots, recommendedLabel }) {
  if (!slots || slots.length === 0) {
    return (
      <div className="parking-grid empty">
        <p>No parking slots available. Loading...</p>
      </div>
    );
  }

  return (
    <div className="parking-grid">
      {slots.map((slot) => (
        <div
          key={slot.id}
          className={`parking-slot ${slot.is_occupied ? 'occupied' : 'available'} ${recommendedLabel === slot.label ? 'recommended' : ''}`}
          title={`${slot.label} - ${slot.is_occupied ? 'Occupied' : 'Available'}`}
        >
          <div className="slot-label">{slot.label}</div>
          {recommendedLabel === slot.label && (
            <div className="slot-status">⭐ Best Empty Slot</div>
          )}
          <div className="slot-status">
            {slot.is_occupied ? '🔴 Occupied' : '🟢 Available'}
          </div>
          <div className="slot-coordinates">
            ({slot.x}, {slot.y}) {slot.w}×{slot.h}
          </div>
        </div>
      ))}
    </div>
  );
}

export default ParkingGrid;
