import React, { useEffect, useRef } from 'react';
import './MaskVisualization.css';

function MaskVisualization({ maskInfo, slots, recommendation }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!maskInfo.has_mask || !canvasRef.current) {
      return;
    }

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    // Set canvas size
    canvas.width = maskInfo.width || 640;
    canvas.height = maskInfo.height || 480;

    // Draw background gradient
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    gradient.addColorStop(0, '#2a3f5f');
    gradient.addColorStop(1, '#1a1a2e');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw only the currently available parking slots passed from the dashboard
    if (slots && slots.length > 0) {
      slots.forEach((slot) => {
        const x = slot.x;
        const y = slot.y;
        const w = slot.w;
        const h = slot.h;

        // Draw slot rectangle
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#27ae60';
        ctx.fillStyle = 'rgba(39, 174, 96, 0.2)';
        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);

        // Draw slot label
        ctx.fillStyle = '#27ae60';
        ctx.font = 'bold 12px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(slot.label, x + w / 2, y + h / 2);
      });
    }

    if (recommendation?.directions?.path?.length > 1) {
      ctx.save();
      ctx.strokeStyle = '#f1c40f';
      ctx.lineWidth = 4;
      ctx.setLineDash([10, 8]);
      ctx.beginPath();
      recommendation.directions.path.forEach((point, index) => {
        if (index === 0) {
          ctx.moveTo(point.x, point.y);
        } else {
          ctx.lineTo(point.x, point.y);
        }
      });
      ctx.stroke();
      ctx.setLineDash([]);

      const entrance = recommendation.directions.path[0];
      ctx.fillStyle = '#f1c40f';
      ctx.beginPath();
      ctx.arc(entrance.x, entrance.y, 7, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillText('Entry', entrance.x + 12, entrance.y - 10);
      ctx.restore();
    }

    // Draw title
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 16px Arial';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText('Available Parking Layout', 10, 10);

    // Draw legend
    const legendY = canvas.height - 50;
    ctx.fillStyle = '#27ae60';
    ctx.fillRect(10, legendY, 15, 15);
    ctx.fillStyle = '#fff';
    ctx.font = '12px Arial';
    ctx.fillText('Available', 30, legendY + 2);

  }, [maskInfo, slots, recommendation]);

  if (!maskInfo.has_mask) {
    return (
      <div className="mask-visualization">
        <p>Mask visualization not available</p>
      </div>
    );
  }

  return (
    <div className="mask-visualization">
      <canvas
        ref={canvasRef}
        className="mask-canvas"
        width={maskInfo.width || 640}
        height={maskInfo.height || 480}
      />
    </div>
  );
}

export default MaskVisualization;
