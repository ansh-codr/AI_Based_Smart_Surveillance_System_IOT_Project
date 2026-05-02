#!/usr/bin/env python3
"""Capture a frame, upload to Firebase Storage, and read Vision results from RTDB."""

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

import cv2
import requests

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    if value.startswith("<<<REPLACE_THIS"):
        raise RuntimeError(f"Environment variable {name} is not configured yet.")
    return value


def normalize_db_url(url: str) -> str:
    return url[:-1] if url.endswith("/") else url


def firebase_sign_in(api_key: str, email: str, password: str) -> str:
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={api_key}"
    )
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True,
    }
    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    data = response.json()
    if "idToken" not in data:
        raise RuntimeError(f"Firebase sign-in failed: {json.dumps(data)}")
    return data["idToken"]


def capture_frame(camera_index: int, output_path: Path) -> None:
    # Prefer Raspberry Pi camera pipeline when Picamera2 is available.
    if Picamera2 is not None:
        cam = Picamera2()
        try:
            cam.configure(cam.create_still_configuration(main={"size": (640, 480)}))
            cam.start()
            frame = cam.capture_array()
            if frame is None:
                raise RuntimeError("Failed to capture frame from Picamera2.")
            bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            saved = cv2.imwrite(str(output_path), bgr)
            if not saved:
                raise RuntimeError(f"Failed to write image to {output_path}")
            return
        finally:
            cam.stop()

    # Fallback to OpenCV for USB/IP cameras.
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


def upload_to_firebase_storage(
    bucket: str,
    storage_path: str,
    image_path: Path,
    id_token: str,
) -> Dict[str, Any]:
    endpoint = (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o"
        f"?uploadType=media&name={quote(storage_path, safe='')}"
    )
    with image_path.open("rb") as image_file:
        image_bytes = image_file.read()

    headers = {
        "Authorization": f"Bearer {id_token}",
        "Content-Type": "image/jpeg",
    }
    response = requests.post(endpoint, headers=headers, data=image_bytes, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_recognition_result(
    db_url: str,
    device_id: str,
    frame_id: str,
    id_token: str,
) -> Optional[Dict[str, Any]]:
    url = (
        f"{db_url}/recognitions/{quote(device_id, safe='')}/"
        f"{quote(frame_id, safe='')}.json?auth={quote(id_token, safe='')}"
    )
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()


def run_once() -> None:
    api_key = required_env("FIREBASE_WEB_API_KEY")
    db_url = normalize_db_url(required_env("FIREBASE_DB_URL"))
    storage_bucket = required_env("FIREBASE_STORAGE_BUCKET")
    email = required_env("DEVICE_USER_EMAIL")
    password = required_env("DEVICE_USER_PASSWORD")
    device_id = required_env("DEVICE_ID")

    camera_index = int(os.getenv("CAMERA_INDEX", "0"))
    poll_timeout_sec = int(os.getenv("POLL_TIMEOUT_SECONDS", "30"))
    poll_interval_sec = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
    image_path = Path(os.getenv("FRAME_IMAGE_PATH", "/tmp/iot_frame.jpg"))

    frame_id = f"{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    storage_path = f"frames/{device_id}/{frame_id}.jpg"

    print("[1/4] Capturing frame...")
    capture_frame(camera_index, image_path)

    print("[2/4] Signing into Firebase...")
    id_token = firebase_sign_in(api_key, email, password)

    print(f"[3/4] Uploading frame to gs://{storage_bucket}/{storage_path}...")
    upload_to_firebase_storage(storage_bucket, storage_path, image_path, id_token)

    print("[4/4] Waiting for recognition result from Realtime Database...")
    deadline = time.time() + poll_timeout_sec
    while time.time() < deadline:
        result = fetch_recognition_result(db_url, device_id, frame_id, id_token)
        if result is not None:
            print("Recognition result:")
            print(json.dumps(result, indent=2))
            if result.get("personDetected", False):
                print("ALERT: Person detected. Trigger your buzzer/relay here.")
            else:
                print("No person detected.")
            return
        time.sleep(poll_interval_sec)

    raise TimeoutError(
        "Timed out waiting for recognition result. "
        "Check Cloud Function logs and database rules."
    )


if __name__ == "__main__":
    run_once()
