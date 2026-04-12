"""Parking detection service - runs parking.py in background"""
import sys
import threading
import logging
from pathlib import Path
from typing import Optional

# Add parent directory to import parking.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from parking import (
    load_mask,
    detect_slots,
    load_classifier,
    resolve_model_path,
    empty_or_not,
    preprocess_frame,
    VIDEO_PATH,
    MASK_PATH,
    STATUS_UPDATE_STEP,
)
import cv2

from services.data_manager import get_manager

logger = logging.getLogger(__name__)


class ParkingDetectorService:
    """Service to run parking detection in background"""

    def __init__(self):
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.logger = logging.getLogger("ParkingDetector")

    def start(self):
        """Start the parking detection service"""
        if self.running:
            self.logger.warning("Parking detector already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_detection, daemon=True)
        self.thread.start()
        self.logger.info("Parking detector started")

    def stop(self):
        """Stop the parking detection service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Parking detector stopped")

    def _run_detection(self):
        """Main detection loop - runs in background thread"""
        try:
            # Load resources
            self.logger.info(f"Loading mask from {MASK_PATH}")
            mask = load_mask(str(MASK_PATH))

            self.logger.info("Detecting parking slots from mask")
            slots = detect_slots(mask)
            self.logger.info(f"Found {len(slots)} parking slots")

            # Load classifier
            self.logger.info("Loading ML classifier")
            model_path = resolve_model_path()
            classifier = load_classifier(model_path)
            if classifier is None:
                self.logger.error("Failed to load classifier")
                return

            # Initialize database with detected slots
            manager = get_manager()
            for idx, slot in enumerate(slots):
                manager.create_or_update_slot(
                    label=slot.label,
                    x=slot.x,
                    y=slot.y,
                    w=slot.w,
                    h=slot.h,
                    is_occupied=False,
                    slot_mask=None
                )
            self.logger.info(f"Initialized {len(slots)} slots in database")

            # Open video
            self.logger.info(f"Opening video from {VIDEO_PATH}")
            cap = cv2.VideoCapture(str(VIDEO_PATH))
            if not cap.isOpened():
                self.logger.error(f"Failed to open video: {VIDEO_PATH}")
                return

            slot_statuses = [False] * len(slots)
            previous_frame = None
            frame_count = 0

            # Main detection loop
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    # Rewind video
                    self.logger.info("Video ended, rewinding...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    previous_frame = None
                    frame_count = 0
                    continue

                frame_count += 1

                # Detect empty slots (runs every STATUS_UPDATE_STEP frames)
                if frame_count % STATUS_UPDATE_STEP == 0:
                    for idx, slot in enumerate(slots):
                        # Extract ROI from frame
                        roi = frame[slot.y:slot.y + slot.h, slot.x:slot.x + slot.w]

                        # Preprocess and predict
                        prep = preprocess_frame(roi, (15, 15))
                        prediction = classifier.predict([prep.flatten()])[0]
                        status = prediction == 0  # True = empty, False = occupied

                        slot_statuses[idx] = status

                        # Update database
                        manager.update_slot_status(
                            label=slot.label,
                            is_occupied=not status  # Invert: status is empty, occupied is inverse
                        )

                    # Log status every 120 frames (~5 sec at 25 fps)
                    if frame_count % (STATUS_UPDATE_STEP * 10) == 0:
                        counts = manager.get_slot_counts()
                        self.logger.info(
                            f"Frame {frame_count}: {counts['available']} available, "
                            f"{counts['occupied']} occupied ({counts['efficiency']}%)"
                        )

                previous_frame = frame.copy()

                # Allow small delay to not block the event loop
                # Use can't use cv2.waitKey because we're in background thread

        except Exception as e:
            self.logger.error(f"Error in parking detection: {e}", exc_info=True)
        finally:
            if 'cap' in locals():
                cap.release()
            self.logger.info("Parking detector stopped")


# Global instance
_service: Optional[ParkingDetectorService] = None


def get_service() -> ParkingDetectorService:
    """Get or create the global parking detector service"""
    global _service
    if _service is None:
        _service = ParkingDetectorService()
    return _service
