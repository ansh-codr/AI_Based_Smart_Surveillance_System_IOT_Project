from __future__ import annotations

import json
import os
import time
from pathlib import Path

import cv2
import face_recognition
import firebase_admin
import numpy as np
from firebase_admin import credentials, db
from flask import Blueprint, Response, jsonify, redirect, request

from ..services.telegram_service import TelegramService

BASE_DIR = Path("/home/pi/Desktop/IOT")
STATUS_FILE = Path(os.getenv("SURVEILLANCE_STATUS_FILE", "/tmp/iot_status.json"))
RAW_FRAME_FILE = Path(os.getenv("SURVEILLANCE_RAW_FRAME_FILE", "/tmp/iot_latest_raw.jpg"))
ANNOTATED_FRAME_FILE = Path(os.getenv("SURVEILLANCE_ANNOTATED_FRAME_FILE", "/tmp/iot_latest_annotated.jpg"))
SCAN_NOW_FILE = Path(os.getenv("SURVEILLANCE_SCAN_NOW_FILE", "/tmp/iot_scan_now.flag"))
RELOAD_FACES_FILE = Path(os.getenv("SURVEILLANCE_RELOAD_FACES_FILE", "/tmp/iot_reload_faces.flag"))
FACES_DIR = Path(os.getenv("FACES_DIR", str(BASE_DIR / "known_faces")))
DEVICE_ID = os.getenv("DEVICE_ID", "pi-cam-01")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "")
FIREBASE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

LIBCAMERA_PATH = "/usr/lib/python3/dist-packages"
if LIBCAMERA_PATH not in os.sys.path:
    os.sys.path.append(LIBCAMERA_PATH)

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except Exception:
    PICAMERA_AVAILABLE = False

try:
    from google.cloud import vision
    VISION_AVAILABLE = True
except Exception:
    VISION_AVAILABLE = False


firebase_app_cache = {}


def _json_default():
    return {
        "device_id": DEVICE_ID,
        "camera": "ALWAYS ONLINE",
        "firebase": "Disconnected",
        "vision_api": "Inactive",
        "pir": "Standby",
        "scan_active": False,
        "seconds_remaining": 0,
        "countdown_label": "PIR: STANDBY",
        "last_motion": None,
        "known_faces_count": 0,
        "known_users": [],
        "last_event": None,
        "timestamp": None,
    }


def _read_status():
    if STATUS_FILE.exists():
        try:
            return {**_json_default(), **json.loads(STATUS_FILE.read_text(encoding="utf-8"))}
        except Exception:
            return _json_default()
    return _json_default()


def _ensure_firebase_app():
    if not FIREBASE_DB_URL or not FIREBASE_CREDENTIALS or not Path(FIREBASE_CREDENTIALS).exists():
        return None
    if "rtdb" in firebase_app_cache:
        return firebase_app_cache["rtdb"]
    try:
        if "rtdb" in firebase_admin._apps:
            firebase_app_cache["rtdb"] = firebase_admin.get_app("rtdb")
            return firebase_app_cache["rtdb"]
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_app_cache["rtdb"] = firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL}, name="rtdb")
        return firebase_app_cache["rtdb"]
    except ValueError:
        firebase_app_cache["rtdb"] = firebase_admin.get_app("rtdb")
        return firebase_app_cache["rtdb"]
    except Exception:
        return None


def _empty_frame(message: str, size=(640, 480)):
    frame = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    cv2.putText(frame, message, (30, size[1] // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    ok, buffer = cv2.imencode('.jpg', frame)
    return buffer.tobytes() if ok else b""


def _multipart_frame(payload: bytes):
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"


def _stream_cached_frame(path: Path, fallback_text: str):
    last_payload = None
    last_mtime = 0.0
    while True:
        payload = last_payload
        try:
            if path.exists():
                stat_result = path.stat()
                if stat_result.st_mtime > last_mtime:
                    payload = path.read_bytes()
                    last_payload = payload
                    last_mtime = stat_result.st_mtime
            if payload is None:
                payload = _empty_frame(fallback_text)
            yield _multipart_frame(payload)
        except Exception:
            yield _multipart_frame(_empty_frame(fallback_text))
        time.sleep(0.08)


def _next_face_filename(person_dir: Path, person_name: str):
    person_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate = person_dir / f"{person_name}{index}.jpg"
        if not candidate.exists():
            return candidate
        index += 1


def _status_response(face_service):
    status = _read_status()
    status["firebase"] = "Connected" if _ensure_firebase_app() is not None else "Disconnected"
    if status.get("vision_api") not in {"Active", "Inactive"}:
        status["vision_api"] = "Active" if VISION_AVAILABLE else "Inactive"
    status["known_users"] = sorted(set(face_service.known_names))
    status["known_faces_count"] = len(face_service.known_encodings)
    return status


def create_blueprint(config, state, events, face_service, firebase_service):
    bp = Blueprint("web", __name__)

    @bp.route("/")
    def index():
        return redirect("/dashboard")

    @bp.route("/dashboard")
    def dashboard():
        dashboard_path = BASE_DIR / "dashboard.html"
        if dashboard_path.exists():
            return dashboard_path.read_text(encoding="utf-8")
        return "<h1>Dashboard not found</h1>", 404

    @bp.route("/video_feed")
    def video_feed():
        return Response(_stream_cached_frame(ANNOTATED_FRAME_FILE, "Camera starting..."), mimetype="multipart/x-mixed-replace; boundary=frame")

    @bp.route("/status")
    def status():
        return jsonify(_status_response(face_service))

    @bp.route("/api/status")
    def api_status():
        return jsonify(_status_response(face_service))

    @bp.route("/api/recognitions")
    def api_recognitions():
        app = _ensure_firebase_app()
        if app is None:
            return jsonify({"events": [], "firebase": "Disconnected"})
        device_id = request.args.get("device", default=DEVICE_ID)
        try:
            data = db.reference(f"recognitions/{device_id}", app=app).get() or {}
        except Exception:
            return jsonify({"events": [], "firebase": "Disconnected"}), 503
        items = [item for item in data.values() if isinstance(item, dict)]
        items.sort(key=lambda item: item.get("timestamp_ms", 0))
        return jsonify({"events": items[-20:][::-1]})

    @bp.route("/events")
    def event_list():
        limit = request.args.get("limit", default=20, type=int)
        return jsonify({"events": events.get_events(limit)})

    @bp.route("/api/camera_status")
    def api_camera_status():
        status = _status_response(face_service)
        return jsonify({
            "active": bool(status.get("scan_active")),
            "seconds_remaining": int(status.get("seconds_remaining") or 0),
            "last_motion": status.get("last_motion"),
            "countdown_label": status.get("countdown_label"),
            "pir": status.get("pir"),
            "camera": status.get("camera"),
            "firebase": status.get("firebase"),
            "vision_api": status.get("vision_api"),
        })

    @bp.route("/api/scan_now", methods=["POST"])
    def api_scan_now():
        try:
            SCAN_NOW_FILE.write_text("1", encoding="utf-8")
            return jsonify({"success": True, "message": "Scan requested"})
        except Exception:
            return jsonify({"success": False, "message": "Scan request failed"}), 500

    @bp.route("/enroll", methods=["POST"])
    def enroll():
        payload = request.get_json(silent=True) or {}
        name = (payload.get("person_name") or payload.get("name") or "").strip()
        if not name or not name.replace("_", "").replace("-", "").isalnum():
            return jsonify({"success": False, "message": "Invalid name"}), 400

        if not RAW_FRAME_FILE.exists():
            return jsonify({"success": False, "message": "No live frame available yet"}), 503

        try:
            image = face_recognition.load_image_file(str(RAW_FRAME_FILE))
            locations = face_recognition.face_locations(image, number_of_times_to_upsample=2, model="hog")
        except Exception:
            return jsonify({"success": False, "message": "Could not inspect live frame"}), 500

        if not locations:
            return jsonify({"success": False, "message": "No face detected, try again"}), 422

        target_dir = FACES_DIR / name
        target_path = _next_face_filename(target_dir, name)
        try:
            bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(target_path), bgr)
        except Exception:
            return jsonify({"success": False, "message": "Save failed"}), 500

        face_service.reload()
        try:
            RELOAD_FACES_FILE.write_text("1", encoding="utf-8")
        except Exception:
            pass

        return jsonify({"success": True, "message": "Enrolled successfully", "saved_as": str(target_path), "known_users": sorted(set(face_service.known_names))})

    @bp.route("/api/enrolled_users")
    def enrolled_users():
        return jsonify({"users": sorted(set(face_service.known_names)), "count": len(face_service.known_encodings)})

    return bp
