"""One-shot parking occupancy agent built on the original parking logic."""

from __future__ import annotations

from dataclasses import dataclass

import cv2

from parking import detect_slots, load_mask, preprocess_frame
from src.models.classifier import load_parking_classifier, predict_is_occupied
from src.utils.data_manager import DataManager
from src.utils.paths import MASKS_DIR, VIDEOS_DIR


DEFAULT_MASK_PATH = MASKS_DIR / "mask.png"
DEFAULT_VIDEO_PATH = VIDEOS_DIR / "parking.mp4"


@dataclass
class ParkingRunResult:
    """Result from a single parking scan."""

    total_slots: int
    occupied_slots: int
    available_slots: int
    video_path: str
    mask_path: str


class ParkingVisionAgent:
    """Run one lightweight parking occupancy pass and store the results."""

    def __init__(self, manager: DataManager) -> None:
        self.manager = manager

    def run_once(self) -> ParkingRunResult:
        """Analyze one frame from the parking video and persist slot states."""
        mask = load_mask(str(DEFAULT_MASK_PATH))
        slots = detect_slots(mask)
        classifier = load_parking_classifier()

        capture = cv2.VideoCapture(str(DEFAULT_VIDEO_PATH))
        if not capture.isOpened():
            raise FileNotFoundError(f"Unable to open parking video: {DEFAULT_VIDEO_PATH}")

        success, frame = capture.read()
        capture.release()
        if not success:
            raise RuntimeError("Unable to read a frame from the parking demo video.")

        mask_height, mask_width = mask.shape[:2]
        prepared_frame = preprocess_frame(frame, (mask_width, mask_height))

        payload = []
        occupied_slots = 0
        for slot in slots:
            roi = prepared_frame[slot.y : slot.y + slot.h, slot.x : slot.x + slot.w]
            is_occupied = predict_is_occupied(classifier, roi)
            occupied_slots += int(is_occupied)
            payload.append(
                {
                    "label": slot.label,
                    "x": slot.x,
                    "y": slot.y,
                    "w": slot.w,
                    "h": slot.h,
                    "is_occupied": is_occupied,
                }
            )

        self.manager.bulk_upsert_slots(payload)
        total_slots = len(payload)
        return ParkingRunResult(
            total_slots=total_slots,
            occupied_slots=occupied_slots,
            available_slots=total_slots - occupied_slots,
            video_path=str(DEFAULT_VIDEO_PATH),
            mask_path=str(DEFAULT_MASK_PATH),
        )
