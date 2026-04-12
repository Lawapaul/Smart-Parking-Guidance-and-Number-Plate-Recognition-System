import os
import re
import sys
import warnings
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import easyocr
import numpy as np
import requests
from PIL import Image

# Suppress PyTorch 2.6+ weights_only warnings
warnings.filterwarnings('ignore', category=UserWarning)

if not hasattr(Image, "ANTIALIAS") and hasattr(Image, "Resampling"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

PROJECT_DIR = Path(__file__).resolve().parent
VIDEO_PATH_CANDIDATES = (
    PROJECT_DIR / "ANPR/car.mp4",
    PROJECT_DIR / "data/videos/plate.mp4",
)
YOLO_MODEL_PATH = PROJECT_DIR / "data/models/yolov8n.pt"
WINDOW_NAME = "Number Plate Detection"
FRAME_SIZE = (960, 540)
OCR_LANGUAGES = ["en"]
EASYOCR_MODEL_DIR = PROJECT_DIR / "easyocr_models"
VEHICLE_CLASS_IDS = {2, 3, 5, 7}
VEHICLE_CONFIDENCE = 0.35
OCR_INTERVAL = 4
BOX_HISTORY_SIZE = 6
TEXT_HISTORY_SIZE = 8
MIN_OCR_CONFIDENCE = 0.25
PLATE_SEARCH_CENTER_TOLERANCE = 0.32

os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")
os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from ultralytics import YOLO

BACKEND_INGEST_URL = "http://127.0.0.1:8000/parking/ingest/vehicle"
BACKEND_TIMEOUT_SECONDS = 1.0


def resolve_video_path() -> Path:
    for candidate in VIDEO_PATH_CANDIDATES:
        if candidate.exists():
            return candidate
    return VIDEO_PATH_CANDIDATES[0]


def stable_box(history: deque[tuple[int, int, int, int]]) -> tuple[int, int, int, int] | None:
    if not history:
        return None
    return tuple(int(sum(values) / len(values)) for values in zip(*history))


def stable_text(history: deque[str]) -> str:
    if not history:
        return ""
    counts: dict[str, int] = {}
    for item in history:
        counts[item] = counts.get(item, 0) + 1
    return max(counts, key=lambda value: (counts[value], len(value)))


def normalize_plate_text(text: str) -> str:
    cleaned = text.upper().replace(" ", "")
    cleaned = cleaned.replace("–", "-").replace("_", "-")
    cleaned = re.sub(r"[^A-Z0-9-]", "", cleaned)
    cleaned = cleaned.replace("O", "0") if re.fullmatch(r"[A-Z]-[0-9O]{3}-[A-Z]{2}", cleaned) else cleaned
    return cleaned


def looks_like_plate(text: str) -> bool:
    compact = text.replace("-", "")
    if len(compact) < 6 or len(compact) > 8:
        return False
    if not any(char.isalpha() for char in compact):
        return False
    if not any(char.isdigit() for char in compact):
        return False
    return True


def choose_target_vehicle(result, frame_shape) -> tuple[int, int, int, int] | None:
    if len(result.boxes) == 0:
        return None

    frame_h, frame_w = frame_shape[:2]
    center_x = frame_w / 2.0
    best_box = None
    best_score = -1.0

    for box in result.boxes:
        class_id = int(box.cls[0].item())
        confidence = float(box.conf[0].item())
        if class_id not in VEHICLE_CLASS_IDS or confidence < VEHICLE_CONFIDENCE:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        area = width * height
        score = (
            confidence * 2.0
            + (area / (frame_w * frame_h)) * 5.0
            + (y2 / frame_h) * 2.0
            + max(0.0, 1.0 - abs(((x1 + x2) / 2.0) - center_x) / frame_w)
        )

        if score > best_score:
            best_score = score
            best_box = (x1, y1, x2, y2)

    return best_box


def preprocess_plate_for_ocr(plate_roi: np.ndarray) -> list[np.ndarray]:
    enlarged = cv2.resize(plate_roi, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    _, binary = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inverted = 255 - binary
    adaptive = cv2.adaptiveThreshold(
        clahe,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        7,
    )
    edges = cv2.Canny(clahe, 80, 180)
    return [enlarged, clahe, binary, inverted, adaptive, edges]


def candidate_score(px: int, py: int, pw: int, ph: int, contour_area: float, search_shape: tuple[int, int]) -> float:
    search_h, search_w = search_shape[:2]
    area = pw * ph
    aspect_ratio = pw / max(ph, 1)
    fill_ratio = contour_area / max(area, 1)
    center_offset = abs((px + pw / 2) - (search_w / 2)) / max(search_w, 1)
    bottom_bias = (py + ph) / max(search_h, 1)

    return (
        area * 0.01
        + contour_area * 0.03
        + max(0.0, 1.0 - abs(aspect_ratio - 3.8)) * 120
        + fill_ratio * 80
        + bottom_bias * 40
        + max(0.0, 1.0 - center_offset / PLATE_SEARCH_CENTER_TOLERANCE) * 120
    )


def extract_plate_candidates(search_roi: np.ndarray) -> list[tuple[int, int, int, int, float]]:
    hsv = cv2.cvtColor(search_roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(search_roi, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    masks = []

    yellow_mask = cv2.inRange(
        hsv,
        np.array([10, 55, 70], dtype=np.uint8),
        np.array([45, 255, 255], dtype=np.uint8),
    )
    white_mask = cv2.inRange(
        hsv,
        np.array([0, 0, 120], dtype=np.uint8),
        np.array([180, 70, 255], dtype=np.uint8),
    )

    for base_mask in (yellow_mask, white_mask):
        cleaned = cv2.morphologyEx(base_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)
        masks.append(cleaned)

    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (17, 5)))
    _, edge_mask = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edge_mask = cv2.morphologyEx(edge_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    masks.append(edge_mask)

    candidates: list[tuple[int, int, int, int, float]] = []
    search_h, search_w = search_roi.shape[:2]

    for mask in masks:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            px, py, pw, ph = cv2.boundingRect(contour)
            area = pw * ph
            if area < 900:
                continue

            aspect_ratio = pw / max(ph, 1)
            if not (2.0 <= aspect_ratio <= 6.8):
                continue

            center_offset = abs((px + pw / 2) - (search_w / 2)) / max(search_w, 1)
            if center_offset > 0.38:
                continue

            if py < int(search_h * 0.1):
                continue

            score = candidate_score(px, py, pw, ph, cv2.contourArea(contour), search_roi.shape)
            candidates.append((px, py, pw, ph, score))

    return sorted(candidates, key=lambda item: item[4], reverse=True)


def locate_plate_in_vehicle(frame: np.ndarray, vehicle_box: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = vehicle_box
    vehicle_roi = frame[y1:y2, x1:x2]
    if vehicle_roi.size == 0:
        return None

    vh, vw = vehicle_roi.shape[:2]
    search_x1 = int(vw * 0.12)
    search_x2 = int(vw * 0.88)
    search_y1 = int(vh * 0.48)
    search_y2 = int(vh * 0.92)
    search_roi = vehicle_roi[search_y1:search_y2, search_x1:search_x2]
    if search_roi.size == 0:
        return None

    candidates = extract_plate_candidates(search_roi)
    if candidates:
        px, py, pw, ph, _ = candidates[0]
        return (
            x1 + search_x1 + px,
            y1 + search_y1 + py,
            x1 + search_x1 + px + pw,
            y1 + search_y1 + py + ph,
        )

    fallback_w = int(vw * 0.32)
    fallback_h = int(vh * 0.11)
    fallback_x = x1 + max(0, (vw - fallback_w) // 2)
    fallback_y = y1 + int(vh * 0.68)
    return (
        fallback_x,
        fallback_y,
        fallback_x + fallback_w,
        min(y2, fallback_y + fallback_h),
    )


def read_plate_text(reader: easyocr.Reader, frame: np.ndarray, plate_box: tuple[int, int, int, int]) -> str:
    x1, y1, x2, y2 = plate_box
    pad_x = max(2, int((x2 - x1) * 0.04))
    pad_y = max(2, int((y2 - y1) * 0.12))
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(frame.shape[1], x2 + pad_x)
    y2 = min(frame.shape[0], y2 + pad_y)

    plate_roi = frame[y1:y2, x1:x2]
    if plate_roi.size == 0:
        return ""

    best_text = ""
    best_confidence = 0.0

    for variant in preprocess_plate_for_ocr(plate_roi):
        results = reader.readtext(
            variant,
            detail=1,
            paragraph=False,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
        )
        for _, text, confidence in results:
            cleaned = normalize_plate_text(text)
            if confidence < MIN_OCR_CONFIDENCE:
                continue
            if not looks_like_plate(cleaned):
                continue
            if confidence > best_confidence:
                best_confidence = float(confidence)
                best_text = cleaned

    return best_text


def vehicle_boxes_are_similar(
    previous_box: tuple[int, int, int, int] | None,
    current_box: tuple[int, int, int, int] | None,
) -> bool:
    if previous_box is None or current_box is None:
        return False

    px1, py1, px2, py2 = previous_box
    cx1, cy1, cx2, cy2 = current_box
    previous_center = ((px1 + px2) / 2, (py1 + py2) / 2)
    current_center = ((cx1 + cx2) / 2, (cy1 + cy2) / 2)
    previous_width = max(1, px2 - px1)
    previous_height = max(1, py2 - py1)

    return (
        abs(previous_center[0] - current_center[0]) <= previous_width * 0.18
        and abs(previous_center[1] - current_center[1]) <= previous_height * 0.18
    )


def draw_overlay(frame: np.ndarray, vehicle_box, plate_box, plate_text: str) -> None:
    if vehicle_box is not None:
        vx1, vy1, vx2, vy2 = vehicle_box
        cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), (255, 180, 0), 2)

    if plate_box is not None:
        px1, py1, px2, py2 = plate_box
        cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 255, 0), 2)
        if plate_text:
            cv2.putText(
                frame,
                plate_text,
                (px1, max(py1 - 10, 28)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

    cv2.putText(frame, "Number Plate Detection", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)
    cv2.putText(
        frame,
        f"Plate: {plate_text if plate_text else 'Searching...'}",
        (15, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
    )


def push_vehicle_to_backend(
    plate_text: str,
    vehicle_box: tuple[int, int, int, int],
    plate_box: Optional[tuple[int, int, int, int]],
) -> None:
    try:
        requests.post(
            BACKEND_INGEST_URL,
            json={
                "plate_text": plate_text,
                "vehicle_bbox": list(vehicle_box),
                "plate_bbox": list(plate_box) if plate_box is not None else None,
            },
            timeout=BACKEND_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        pass


def main() -> int:
    video_path = resolve_video_path()
    if not video_path.exists():
        print(f"Missing project video: {video_path}")
        return 1
    if not YOLO_MODEL_PATH.exists():
        print(f"Missing YOLO model: {YOLO_MODEL_PATH}")
        return 1

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Unable to open video file: {video_path}")
        return 1

    EASYOCR_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    reader = easyocr.Reader(OCR_LANGUAGES, model_storage_directory=str(EASYOCR_MODEL_DIR))
    model = YOLO(str(YOLO_MODEL_PATH))

    vehicle_history: deque[tuple[int, int, int, int]] = deque(maxlen=BOX_HISTORY_SIZE)
    plate_history: deque[tuple[int, int, int, int]] = deque(maxlen=BOX_HISTORY_SIZE)
    text_history: deque[str] = deque(maxlen=TEXT_HISTORY_SIZE)
    frame_number = 0
    last_sent_plate = ""
    last_vehicle_for_text: tuple[int, int, int, int] | None = None

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    while True:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            vehicle_history.clear()
            plate_history.clear()
            text_history.clear()
            frame_number = 0
            continue

        frame = cv2.resize(frame, FRAME_SIZE, interpolation=cv2.INTER_LINEAR)
        result = model(frame, verbose=False)[0]

        vehicle_box = choose_target_vehicle(result, frame.shape)
        if vehicle_box is not None:
            vehicle_history.append(vehicle_box)

        stable_vehicle = stable_box(vehicle_history)
        if not vehicle_boxes_are_similar(last_vehicle_for_text, stable_vehicle):
            plate_history.clear()
            text_history.clear()
            last_sent_plate = ""
        last_vehicle_for_text = stable_vehicle

        if stable_vehicle is not None:
            plate_box = locate_plate_in_vehicle(frame, stable_vehicle)
            if plate_box is not None:
                plate_history.append(plate_box)

        stable_plate = stable_box(plate_history)
        if stable_plate is not None and frame_number % OCR_INTERVAL == 0:
            plate_text = read_plate_text(reader, frame, stable_plate)
            if plate_text:
                text_history.append(plate_text)

        stable_plate_text = stable_text(text_history)
        if stable_vehicle is not None and stable_plate_text and stable_plate_text != last_sent_plate:
            push_vehicle_to_backend(stable_plate_text, stable_vehicle, stable_plate)
            last_sent_plate = stable_plate_text

        draw_overlay(frame, stable_vehicle, stable_plate, stable_plate_text)
        cv2.imshow(WINDOW_NAME, frame)

        key = cv2.waitKey(25) & 0xFF
        if key == 27:
            break

        frame_number += 1

    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
