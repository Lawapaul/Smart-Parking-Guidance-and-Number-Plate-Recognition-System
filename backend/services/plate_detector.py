"""Plate detection service - runs plate.py detection in background"""
import os
import sys
import threading
import logging
from pathlib import Path
from typing import Optional
from collections import deque

import cv2
import easyocr

# Add parent directory to import plate.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")
os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from plate import (
    choose_target_vehicle,
    locate_plate_in_vehicle,
    read_plate_text,
    stable_box,
    stable_text,
    normalize_plate_text,
    resolve_video_path,
    YOLO_MODEL_PATH,
    resolve_plate_model_path,
    BOX_HISTORY_SIZE,
    TEXT_HISTORY_SIZE,
    OCR_INTERVAL,
    VEHICLE_CLASS_IDS,
    VEHICLE_CONFIDENCE,
    FRAME_SIZE,
    OCR_LANGUAGES,
    EASYOCR_MODEL_DIR,
)
from ultralytics import YOLO

from services.data_manager import get_manager

logger = logging.getLogger(__name__)


class PlateDetectorService:
    """Service to run plate detection in background"""

    def __init__(self):
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.logger = logging.getLogger("PlateDetector")

    def start(self):
        """Start the plate detection service"""
        if self.running:
            self.logger.warning("Plate detector already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_detection, daemon=True)
        self.thread.start()
        self.logger.info("Plate detector started")

    def stop(self):
        """Stop the plate detection service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("Plate detector stopped")

    def _run_detection(self):
        """Main detection loop - runs in background thread"""
        try:
            plate_video_path = resolve_video_path()
            # Check dependencies
            if not Path(plate_video_path).exists():
                self.logger.error(f"Video not found: {plate_video_path}")
                return

            if not Path(YOLO_MODEL_PATH).exists():
                self.logger.error(f"YOLO model not found: {YOLO_MODEL_PATH}")
                return
            plate_model_path = resolve_plate_model_path()
            if not Path(plate_model_path).exists():
                self.logger.error(f"Plate model not found: {plate_model_path}")
                return

            EASYOCR_MODEL_DIR.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Initializing EasyOCR from {EASYOCR_MODEL_DIR}")
            reader = easyocr.Reader(
                OCR_LANGUAGES,
                model_storage_directory=str(EASYOCR_MODEL_DIR)
            )

            # Load YOLO model
            self.logger.info(f"Loading YOLO model from {YOLO_MODEL_PATH}")
            yolo_model = YOLO(str(YOLO_MODEL_PATH))
            self.logger.info(f"Loading plate model from {plate_model_path}")
            plate_model = YOLO(str(plate_model_path))

            # Open video
            self.logger.info(f"Opening video from {plate_video_path}")
            cap = cv2.VideoCapture(str(plate_video_path))
            if not cap.isOpened():
                self.logger.error(f"Failed to open video: {plate_video_path}")
                return

            # Initialize history deques
            box_history: deque = deque(maxlen=BOX_HISTORY_SIZE)
            plate_box_history: deque = deque(maxlen=BOX_HISTORY_SIZE)
            text_history: deque = deque(maxlen=TEXT_HISTORY_SIZE)
            frame_count = 0

            # Main detection loop
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    # Rewind video
                    self.logger.info("Plate video ended, rewinding...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    box_history.clear()
                    plate_box_history.clear()
                    text_history.clear()
                    frame_count = 0
                    continue

                frame_count += 1

                try:
                    frame = cv2.resize(frame, FRAME_SIZE, interpolation=cv2.INTER_LINEAR)

                    # Detect vehicles
                    result = yolo_model(frame, verbose=False)[0]
                    vehicle_box = choose_target_vehicle(result, frame.shape)

                    if vehicle_box is not None:
                        box_history.append(vehicle_box)

                    stable_vehicle_box = stable_box(box_history)

                    if stable_vehicle_box is not None:
                        plate_box = locate_plate_in_vehicle(frame, stable_vehicle_box, plate_model)
                        if plate_box is not None:
                            plate_box_history.append(plate_box)

                    stable_plate_box = stable_box(plate_box_history)
                    if stable_plate_box is not None and frame_count % OCR_INTERVAL == 0:
                        plate_text = read_plate_text(reader, frame, stable_plate_box)
                        if plate_text:
                            normalized_text = normalize_plate_text(plate_text)
                            if normalized_text:
                                text_history.append(normalized_text)

                    stable_plate_text = stable_text(text_history)
                    if stable_vehicle_box is not None and stable_plate_text:
                        x1, y1, x2, y2 = stable_vehicle_box
                        manager = get_manager()
                        manager.add_vehicle(
                            plate_text=stable_plate_text,
                            vehicle_x1=x1,
                            vehicle_y1=y1,
                            vehicle_x2=x2,
                            vehicle_y2=y2,
                            plate_x1=stable_plate_box[0] if stable_plate_box else None,
                            plate_y1=stable_plate_box[1] if stable_plate_box else None,
                            plate_x2=stable_plate_box[2] if stable_plate_box else None,
                            plate_y2=stable_plate_box[3] if stable_plate_box else None
                        )
                        self.logger.info(f"Detected plate: {stable_plate_text}")

                except Exception as e:
                    self.logger.warning(f"Error processing frame {frame_count}: {e}")

        except Exception as e:
            self.logger.error(f"Error in plate detection: {e}", exc_info=True)
        finally:
            if 'cap' in locals():
                cap.release()
            self.logger.info("Plate detector stopped")


# Global instance
_service: Optional[PlateDetectorService] = None


def get_service() -> PlateDetectorService:
    """Get or create the global plate detector service"""
    global _service
    if _service is None:
        _service = PlateDetectorService()
    return _service
