import React from 'react';
import './VehicleDetections.css';

function VehicleDetections({ vehicles }) {
  if (!vehicles || vehicles.length === 0) {
    return (
      <div className="vehicle-detections empty">
        <p>No vehicles detected yet</p>
      </div>
    );
  }

  // Show only latest 10 vehicles
  const recentVehicles = vehicles.slice(0, 10);

  return (
    <div className="vehicle-detections">
      {recentVehicles.map((vehicle) => (
        <div key={vehicle.id} className="vehicle-card">
          <div className="vehicle-plate">{vehicle.plate_text}</div>
          <div className="vehicle-details">
            <div className="detail-row">
              <span className="label">Detected:</span>
              <span className="value">
                {new Date(vehicle.detected_at).toLocaleTimeString()}
              </span>
            </div>
            {vehicle.vehicle_bbox && (
              <div className="detail-row">
                <span className="label">Position:</span>
                <span className="value">
                  ({vehicle.vehicle_bbox[0]}, {vehicle.vehicle_bbox[1]})
                </span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default VehicleDetections;
