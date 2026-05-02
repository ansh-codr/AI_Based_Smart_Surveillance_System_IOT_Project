#!/usr/bin/env python3
"""Capture a frame and run Google Cloud Vision directly from device."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import cv2
from google.cloud import vision


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    if value.startswith("<<<REPLACE_THIS"):
        raise RuntimeError(f"Environment variable {name} is not configured yet.")
    return value


def capture_frame(camera_index: int, output_path: Path) -> None:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera. Check CAMERA_INDEX and camera wiring.")

    try:
        for _ in range(5):
            cap.read()
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError("Failed to capture frame from camera.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        saved = cv2.imwrite(str(output_path), frame)
        if not saved:
            raise RuntimeError(f"Failed to write image to {output_path}")
    finally:
        cap.release()


def analyze_image(image_path: Path) -> Dict[str, Any]:
    client = vision.ImageAnnotatorClient()

    with image_path.open("rb") as image_file:
        image = vision.Image(content=image_file.read())

    response = client.annotate_image(
        {
            "image": image,
            "features": [
                {"type_": vision.Feature.Type.LABEL_DETECTION, "max_results": 10},
                {"type_": vision.Feature.Type.FACE_DETECTION, "max_results": 10},
                {
                    "type_": vision.Feature.Type.OBJECT_LOCALIZATION,
                    "max_results": 10,
                },
            ],
        }
    )

    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    labels: List[Dict[str, Any]] = [
        {"description": item.description, "score": float(item.score)}
        for item in response.label_annotations
    ]
    objects: List[Dict[str, Any]] = [
        {"name": item.name, "score": float(item.score)}
        for item in response.localized_object_annotations
    ]

    faces_count = len(response.face_annotations)

    person_by_label = any(
        "person" in label["description"].lower() or "human" in label["description"].lower()
        for label in labels
    )
    person_by_object = any(
        "person" in obj["name"].lower() or "human" in obj["name"].lower()
        for obj in objects
    )

    person_detected = person_by_label or person_by_object or faces_count > 0

    return {
        "labels": labels,
        "objects": objects,
        "facesCount": faces_count,
        "personDetected": person_detected,
    }


def run_once() -> None:
    required_env("GOOGLE_APPLICATION_CREDENTIALS")

    camera_index = int(os.getenv("CAMERA_INDEX", "0"))
    image_path = Path(os.getenv("FRAME_IMAGE_PATH", "/tmp/direct_vision_frame.jpg"))

    print("[1/2] Capturing frame...")
    capture_frame(camera_index, image_path)

    print("[2/2] Sending frame to Google Cloud Vision API...")
    result = analyze_image(image_path)
    print(json.dumps(result, indent=2))

    if result["personDetected"]:
        print("ALERT: Person detected. Trigger your buzzer/relay here.")
    else:
        print("No person detected.")


if __name__ == "__main__":
    run_once()
