import sys
import pickle
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests


VIDEO_PATH = "/Users/harshitsingh/Developer/Machine Vision Project/data/videos/parking.mp4"
MASK_PATH = "/Users/harshitsingh/Developer/Machine Vision Project/data/masks/mask.png"
WINDOW_NAME = "SMART PARKING SYSTEM"
DISPLAY_SIZE = (1280, 720)
MIN_SLOT_WIDTH = 20
MIN_SLOT_HEIGHT = 20
ROW_GAP_FACTOR = 0.6
STATUS_UPDATE_STEP = 12
MOTION_DIFF_RATIO = 0.35
MODEL_INPUT_SIZE = (15, 15)
MODEL_PATH_CANDIDATES = (
    Path("/Users/harshitsingh/Developer/Machine Vision Project/data/models/weights/model.p"),
    Path("/Users/harshitsingh/Developer/Machine Vision Project/model.p"),
    Path("/Users/harshitsingh/Downloads/parking-space-counter/model/model.p"),
)
BACKEND_INGEST_URL = "http://127.0.0.1:8000/parking/ingest/slots"
BACKEND_TIMEOUT_SECONDS = 1.0


@dataclass(frozen=True)
class ParkingSlot:
    label: str
    x: int
    y: int
    w: int
    h: int
    slot_mask: np.ndarray


def load_mask(mask_path: str) -> np.ndarray:
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise FileNotFoundError(f"Unable to load mask image: {mask_path}")
    return mask


def group_rows(boxes: list[tuple[int, int, int, int]]) -> list[list[tuple[int, int, int, int]]]:
    if not boxes:
        return []

    sorted_boxes = sorted(boxes, key=lambda box: (box[1], box[0]))
    average_height = sum(box[3] for box in sorted_boxes) / len(sorted_boxes)
    row_gap = max(15, int(average_height * ROW_GAP_FACTOR))

    rows: list[list[tuple[int, int, int, int]]] = []
    current_row: list[tuple[int, int, int, int]] = [sorted_boxes[0]]
    current_y = sorted_boxes[0][1]

    for box in sorted_boxes[1:]:
        if abs(box[1] - current_y) <= row_gap:
            current_row.append(box)
            current_y = int((current_y + box[1]) / 2)
        else:
            rows.append(sorted(current_row, key=lambda item: item[0]))
            current_row = [box]
            current_y = box[1]

    rows.append(sorted(current_row, key=lambda item: item[0]))
    return rows


def detect_slots(mask: np.ndarray) -> list[ParkingSlot]:
    _, binary_mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
    connected_components = cv2.connectedComponentsWithStats(binary_mask, 4, cv2.CV_32S)
    total_labels, _, stats, _ = connected_components

    box_data: list[tuple[int, int, int, int]] = []
    for label_index in range(1, total_labels):
        x = int(stats[label_index, cv2.CC_STAT_LEFT])
        y = int(stats[label_index, cv2.CC_STAT_TOP])
        w = int(stats[label_index, cv2.CC_STAT_WIDTH])
        h = int(stats[label_index, cv2.CC_STAT_HEIGHT])
        if w < MIN_SLOT_WIDTH or h < MIN_SLOT_HEIGHT:
            continue
        box_data.append((x, y, w, h))

    rows = group_rows(box_data)

    slots: list[ParkingSlot] = []
    for row_index, row in enumerate(rows, start=1):
        for slot_index, box in enumerate(row, start=1):
            x, y, w, h = box
            slot_mask = binary_mask[y : y + h, x : x + w]
            slots.append(
                ParkingSlot(
                    label=f"P{row_index}-S{slot_index}",
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    slot_mask=slot_mask,
                )
            )

    return slots


def preprocess_frame(frame: np.ndarray, target_size: tuple[int, int]) -> np.ndarray:
    frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_LINEAR)
    return frame


def calc_diff(current_roi: np.ndarray, previous_roi: np.ndarray) -> float:
    return float(np.abs(np.mean(current_roi) - np.mean(previous_roi)))


def resolve_model_path() -> Path:
    for candidate in MODEL_PATH_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to find model.p for parking space classification.")


def load_classifier(model_path: Path):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with model_path.open("rb") as model_file:
            return pickle.load(model_file)


def empty_or_not(model, spot_bgr: np.ndarray) -> bool:
    resized_spot = cv2.resize(spot_bgr, MODEL_INPUT_SIZE, interpolation=cv2.INTER_AREA)
    sample = resized_spot.astype(np.float32) / 255.0
    prediction = int(model.predict(sample.reshape(1, -1))[0])
    return prediction == 0


def rewind_video(capture: cv2.VideoCapture) -> bool:
    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
    success, _ = capture.read()
    if not success:
        return False
    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return True


def draw_header(frame: np.ndarray, vehicle_count: int, total_slots: int, efficiency: float) -> None:
    title = "SMART PARKING SYSTEM"
    text_size, _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)
    title_x = max((frame.shape[1] - text_size[0]) // 2, 20)

    cv2.putText(frame, title, (title_x, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
    cv2.putText(frame, f"Vehicle Count: {vehicle_count}", (25, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Total Slots: {total_slots}", (25, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Efficiency: {efficiency:.1f}%", (25, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)


def build_slot_payload(slots: list[ParkingSlot], slot_statuses: list[bool]) -> dict[str, Any]:
    return {
        "slots": [
            {
                "label": slot.label,
                "x": slot.x,
                "y": slot.y,
                "w": slot.w,
                "h": slot.h,
                "is_occupied": bool(slot_statuses[index]),
            }
            for index, slot in enumerate(slots)
        ]
    }


def push_slots_to_backend(slots: list[ParkingSlot], slot_statuses: list[bool]) -> None:
    payload = build_slot_payload(slots, slot_statuses)
    try:
        requests.post(BACKEND_INGEST_URL, json=payload, timeout=BACKEND_TIMEOUT_SECONDS)
    except requests.RequestException:
        pass


def main() -> int:
    try:
        mask = load_mask(MASK_PATH)
    except FileNotFoundError as error:
        print(error)
        return 1

    try:
        model_path = resolve_model_path()
        classifier = load_classifier(model_path)
    except FileNotFoundError as error:
        print(error)
        return 1

    slots = detect_slots(mask)
    if not slots:
        print("No parking slots detected from mask.png")
        return 1

    capture = cv2.VideoCapture(VIDEO_PATH)
    if not capture.isOpened():
        print(f"Unable to open video file: {VIDEO_PATH}")
        return 1

    mask_height, mask_width = mask.shape[:2]
    frame_size = (mask_width, mask_height)
    slot_statuses = [True] * len(slots)
    previous_frame: np.ndarray | None = None
    frame_number = 0

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, *DISPLAY_SIZE)

    while True:
        success, frame = capture.read()
        if not success:
            cap_reset = capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            if not cap_reset and not rewind_video(capture):
                print("Reached the end of the video and could not loop it.")
                break
            previous_frame = None
            frame_number = 0
            continue

        display_frame = preprocess_frame(frame, frame_size)
        slots_to_update: list[int]

        if frame_number % STATUS_UPDATE_STEP == 0:
            if previous_frame is None:
                slots_to_update = list(range(len(slots)))
            else:
                diffs = []
                for index, slot in enumerate(slots):
                    current_roi = display_frame[slot.y : slot.y + slot.h, slot.x : slot.x + slot.w]
                    previous_roi = previous_frame[slot.y : slot.y + slot.h, slot.x : slot.x + slot.w]
                    diffs.append((index, calc_diff(current_roi, previous_roi)))

                max_diff = max((diff for _, diff in diffs), default=0.0)
                if max_diff <= 0:
                    slots_to_update = []
                else:
                    slots_to_update = [
                        index
                        for index, diff in diffs
                        if diff / max_diff >= MOTION_DIFF_RATIO
                    ]

            for slot_index in slots_to_update:
                slot = slots[slot_index]
                spot_crop = display_frame[slot.y : slot.y + slot.h, slot.x : slot.x + slot.w]
                slot_statuses[slot_index] = not empty_or_not(classifier, spot_crop)

            previous_frame = display_frame.copy()
            push_slots_to_backend(slots, slot_statuses)

        occupied_count = 0
        for slot_index, slot in enumerate(slots):
            is_occupied = slot_statuses[slot_index]
            if is_occupied:
                occupied_count += 1

            color = (0, 0, 255) if is_occupied else (0, 255, 0)
            thickness = 2 if is_occupied else 3
            cv2.rectangle(display_frame, (slot.x, slot.y), (slot.x + slot.w, slot.y + slot.h), color, thickness)

            if slot.h >= 24:
                label_y = slot.y + min(slot.h - 6, 14)
            else:
                label_y = max(slot.y - 4, 18)

            cv2.putText(
                display_frame,
                slot.label,
                (slot.x + 2, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.32,
                color,
                1,
                cv2.LINE_AA,
            )

        total_slots = len(slots)
        efficiency = (occupied_count / total_slots) * 100 if total_slots else 0.0
        draw_header(display_frame, occupied_count, total_slots, efficiency)

        screen_frame = cv2.resize(display_frame, DISPLAY_SIZE, interpolation=cv2.INTER_AREA)
        cv2.imshow(WINDOW_NAME, screen_frame)

        key = cv2.waitKey(25) & 0xFF
        if key == 27:
            break

        frame_number += 1

    capture.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
