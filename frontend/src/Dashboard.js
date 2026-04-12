import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ParkingGrid from './ParkingGrid';
import VehicleDetections from './VehicleDetections';
import MaskVisualization from './components/MaskVisualization';
import './Dashboard.css';

const API_BASE_URL = 'http://localhost:8000';

function Dashboard() {
  const [slots, setSlots] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [stats, setStats] = useState({
    total: 0,
    available: 0,
    occupied: 0,
    efficiency: 0
  });
  const [maskInfo, setMaskInfo] = useState({ width: 0, height: 0, has_mask: false });
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [error, setError] = useState(null);
  const latestVehicle = vehicles.length > 0 ? vehicles[0] : null;

  useEffect(() => {
    // Fetch data on component mount and set up polling
    fetchAllData();
    const interval = setInterval(fetchAllData, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, []);

  const fetchAllData = async () => {
    try {
      setError(null);

      // Fetch all slots with stats
      const slotsResponse = await axios.get(`${API_BASE_URL}/parking/slots`, {
        timeout: 5000
      });

      if (slotsResponse.data) {
        setSlots(slotsResponse.data.slots || []);
        setStats({
          total: slotsResponse.data.total,
          available: slotsResponse.data.available,
          occupied: slotsResponse.data.occupied,
          efficiency: slotsResponse.data.efficiency
        });
      }

      // Fetch vehicles
      const vehiclesResponse = await axios.get(`${API_BASE_URL}/parking/vehicles`, {
        timeout: 5000
      });

      if (vehiclesResponse.data) {
        setVehicles(vehiclesResponse.data.vehicles || []);
      }

      // Fetch mask info
      const maskResponse = await axios.get(`${API_BASE_URL}/parking/mask-info`, {
        timeout: 5000
      });

      if (maskResponse.data) {
        setMaskInfo(maskResponse.data);
      }

      const recommendationResponse = await axios.get(`${API_BASE_URL}/parking/slots/recommendation`, {
        timeout: 5000
      });

      if (recommendationResponse.data) {
        setRecommendation(recommendationResponse.data.recommendation || null);
      }

      setLastUpdate(new Date());
      setLoading(false);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError(err.message || 'Failed to fetch data from server');
      // Don't set loading to false on error to keep showing last data
    }
  };

  if (loading) {
    return (
      <div className="dashboard loading">
        <div style={{ textAlign: 'center', padding: '60px 20px' }}>
          <h1>Smart Parking System</h1>
          <p>Loading data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="header">
        <h1>🅿️ Smart Parking Management System</h1>
        <p className="loading-indicator">
          {error ? '⚠️ ' + error : '✓ Real-time detection active'}
        </p>
      </div>

      {/* Statistics Cards */}
      <div className="stats-container">
        <div className="stat-card total">
          <div className="stat-icon">🅿️</div>
          <div className="stat-info">
            <p className="stat-label">Total Slots</p>
            <h2>{stats.total}</h2>
          </div>
        </div>

        <div className="stat-card available">
          <div className="stat-icon">🟢</div>
          <div className="stat-info">
            <p className="stat-label">Available</p>
            <h2>{stats.available}</h2>
          </div>
        </div>

        <div className="stat-card occupied">
          <div className="stat-icon">🔴</div>
          <div className="stat-info">
            <p className="stat-label">Occupied</p>
            <h2>{stats.occupied}</h2>
          </div>
        </div>

        <div className="stat-card efficiency">
          <div className="stat-icon">📊</div>
          <div className="stat-info">
            <p className="stat-label">Efficiency</p>
            <h2>{stats.efficiency || 0}%</h2>
          </div>
        </div>
      </div>

      <div className="plate-banner">
        <div className="plate-banner-copy">
          <p className="plate-banner-label">Latest Number Plate Detected</p>
          <div className="plate-banner-value">
            {latestVehicle?.plate_text || 'Waiting for plate detection...'}
          </div>
          <p className="plate-banner-time">
            {latestVehicle?.detected_at
              ? `Detected at ${new Date(latestVehicle.detected_at).toLocaleTimeString()}`
              : 'Start plate detection to see vehicle numbers here.'}
          </p>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="content-grid">
        {/* Parking Grid Section */}
        <div className="section">
          <h2>🅿️ Parking Slots Status</h2>
          {recommendation?.slot && (
            <div style={{
              marginBottom: '16px',
              padding: '16px',
              borderRadius: '16px',
              background: 'linear-gradient(135deg, rgba(39, 174, 96, 0.18), rgba(46, 204, 113, 0.08))',
              border: '1px solid rgba(39, 174, 96, 0.35)'
            }}>
              <strong>Recommended Empty Slot: {recommendation.slot.label}</strong>
              <p style={{ margin: '8px 0 0 0' }}>
                {recommendation.directions?.text}
              </p>
            </div>
          )}
          <ParkingGrid
            slots={slots}
            recommendedLabel={recommendation?.slot?.label || null}
          />
        </div>

        {/* Mask Visualization Section */}
        {maskInfo.has_mask && (
          <div className="section">
            <h2>🗺️ Parking Layout</h2>
            <MaskVisualization
              maskInfo={maskInfo}
              slots={slots}
              recommendation={recommendation}
            />
          </div>
        )}
      </div>

      {/* Vehicles Section */}
      <div className="section full-width">
        <h2>🚗 Detected Vehicles</h2>
        <VehicleDetections vehicles={vehicles} />
      </div>

      {/* Footer */}
      <div className="footer">
        <p>Last updated: {lastUpdate.toLocaleTimeString()}</p>
        <p>API: {error ? '❌ Disconnected' : '✓ Connected'}</p>
      </div>
    </div>
  );
}

export default Dashboard;
