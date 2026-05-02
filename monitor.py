#!/usr/bin/env python3
"""Always-on CCTV surveillance daemon.

This process owns the camera and GPIO hardware. It keeps the camera streaming
continuously, uses PIR motion to open a 20-second recognition window, runs
local face recognition plus Google Vision labels on every active frame, writes
results to Firebase RTDB, and sends Telegram alerts.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import cv2
import face_recognition
import numpy as np
import requests

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
except Exception:
    FIREBASE_AVAILABLE = False

try:
    from google.cloud import vision
    VISION_AVAILABLE = True
except Exception:
    VISION_AVAILABLE = False

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except Exception:
    PICAMERA_AVAILABLE = False

from telegram import Bot


BASE_DIR = Path("/home/pi/Desktop/IOT")
FACES_DIR = Path(os.getenv("FACES_DIR", str(BASE_DIR / "known_faces")))
DEVICE_ID = os.getenv("DEVICE_ID", "pi-cam-01")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL", "")
FIREBASE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

PIR_PIN = int(os.getenv("PIR_PIN", "23"))
GREEN_LED_PIN = int(os.getenv("GREEN_PIN", "17"))
RED_LED_PIN = int(os.getenv("RED_PIN", "27"))
BUZZER_PIN = int(os.getenv("BUZZER_PIN", "22"))
FACE_TOLERANCE = float(os.getenv("FACE_TOLERANCE", "0.45"))
FACE_UPSAMPLE = int(os.getenv("FACE_UPSAMPLE", "2"))
SCAN_WINDOW_SECONDS = int(os.getenv("SCAN_WINDOW_SECONDS", "20"))
CAMERA_WIDTH = int(os.getenv("FRAME_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("FRAME_HEIGHT", "480"))
IDLE_SLEEP_SECONDS = float(os.getenv("IDLE_SLEEP_SECONDS", "0.08"))
ACTIVE_SLEEP_SECONDS = float(os.getenv("ACTIVE_SLEEP_SECONDS", "0.10"))
STATUS_FILE = Path(os.getenv("SURVEILLANCE_STATUS_FILE", "/tmp/iot_status.json"))
RAW_FRAME_FILE = Path(os.getenv("SURVEILLANCE_RAW_FRAME_FILE", "/tmp/iot_latest_raw.jpg"))
ANNOTATED_FRAME_FILE = Path(os.getenv("SURVEILLANCE_ANNOTATED_FRAME_FILE", "/tmp/iot_latest_annotated.jpg"))
SCAN_NOW_FILE = Path(os.getenv("SURVEILLANCE_SCAN_NOW_FILE", "/tmp/iot_scan_now.flag"))
RELOAD_FACES_FILE = Path(os.getenv("SURVEILLANCE_RELOAD_FACES_FILE", "/tmp/iot_reload_faces.flag"))
MONITOR_LOG = BASE_DIR / "monitor.log"


@dataclass
class EventResult:
    name: str
    status: str
    confidence: float
    vision_labels: list[str]
    telegram_sent: bool
    timestamp_ms: int
    timestamp_iso: str


class SurveillanceDaemon:
    def __init__(self):
        self.camera = None
        self.vision_client = None
        self.telegram_bot = None
        self.telegram_enabled = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        self.firebase_app = None
        self.known_encodings: list[np.ndarray] = []
        self.known_names: list[str] = []
        self.gpio_ready = False
        self.firebase_ready = False
        self.vision_ready = False
        self.reload_lock = Lock()
        self.last_motion_time = 0.0
        self.last_motion_wallclock = 0.0
        self.scan_active_until = 0.0
        self.last_status_write = 0.0
        self.last_frame_result: dict | None = None
        self._init_gpio()
        self._init_camera()
        self._init_firebase()
        self._init_vision()
        self._init_telegram()
        self.reload_known_faces(initial=True)

    def _log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        print(line, flush=True)
        try:
            with MONITOR_LOG.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception:
            pass

    def _init_gpio(self):
        if not GPIO_AVAILABLE:
            self._log("[GPIO] RPi.GPIO unavailable; running in soft mode")
            return
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(PIR_PIN, GPIO.IN)
            GPIO.setup(GREEN_LED_PIN, GPIO.OUT)
            GPIO.setup(RED_LED_PIN, GPIO.OUT)
            GPIO.setup(BUZZER_PIN, GPIO.OUT)
            GPIO.output(GREEN_LED_PIN, GPIO.LOW)
            GPIO.output(RED_LED_PIN, GPIO.LOW)
            GPIO.output(BUZZER_PIN, GPIO.LOW)
            self.gpio_ready = True
            self._log(f"[GPIO] Ready on PIR={PIR_PIN}, GREEN={GREEN_LED_PIN}, RED={RED_LED_PIN}, BUZZER={BUZZER_PIN}")
        except Exception as exc:
            self.gpio_ready = False
            self._log(f"[GPIO] Init failed: {exc}")

    def _init_camera(self):
        if not PICAMERA_AVAILABLE:
            self._log("[CAMERA] Picamera2 unavailable")
            return
        try:
            self.camera = Picamera2()
            self.camera.configure(
                self.camera.create_preview_configuration(
                    main={"format": "RGB888", "size": (CAMERA_WIDTH, CAMERA_HEIGHT)}
                )
            )
            self.camera.start()
            self._log("[CAMERA] Picamera2 started")
        except Exception as exc:
            self.camera = None
            self._log(f"[CAMERA] Init failed: {exc}")

    def _init_firebase(self):
        if not FIREBASE_AVAILABLE:
            self._log("[FIREBASE] firebase_admin unavailable")
            return
        if not FIREBASE_DB_URL or not FIREBASE_CREDENTIALS or not Path(FIREBASE_CREDENTIALS).exists():
            self._log("[FIREBASE] Missing database URL or credentials")
            return
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
            self.firebase_app = firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL}, name="surveillance")
            self.firebase_ready = True
            self._log("[FIREBASE] RTDB connected")
        except ValueError:
            self.firebase_app = firebase_admin.get_app("surveillance")
            self.firebase_ready = True
            self._log("[FIREBASE] RTDB re-used existing app")
        except Exception as exc:
            self.firebase_ready = False
            self._log(f"[FIREBASE] Init failed: {exc}")

    def _init_vision(self):
        if not VISION_AVAILABLE:
            self._log("[VISION] google-cloud-vision unavailable")
            return
        try:
            self.vision_client = vision.ImageAnnotatorClient()
            self.vision_ready = True
            self._log("[VISION] Client ready")
        except Exception as exc:
            self.vision_client = None
            self.vision_ready = False
            self._log(f"[VISION] Init failed: {exc}")

    def _init_telegram(self):
        if not self.telegram_enabled:
            self._log("[TELEGRAM] Token/chat ID not configured")
            return
        try:
            self.telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN)
            self._log("[TELEGRAM] Bot configured")
        except Exception as exc:
            self.telegram_bot = None
            self.telegram_enabled = False
            self._log(f"[TELEGRAM] Init failed: {exc}")

    def _write_json(self, path: Path, payload: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _save_frame(self, path: Path, frame: np.ndarray):
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            return False
        temp_path.write_bytes(buffer.tobytes())
        temp_path.replace(path)
        return True

    def _load_face_image(self, file_path: Path):
        image = face_recognition.load_image_file(str(file_path))
        encodings = face_recognition.face_encodings(image)
        if not encodings:
            return None
        return encodings[0]

    def reload_known_faces(self, initial: bool = False):
        with self.reload_lock:
            encodings: list[np.ndarray] = []
            names: list[str] = []
            if FACES_DIR.exists():
                for image_path in sorted(FACES_DIR.rglob("*")):
                    if not image_path.is_file() or image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                        continue
                    person_name = image_path.parent.name
                    try:
                        encoding = self._load_face_image(image_path)
                        if encoding is None:
                            self._log(f"[FACES] No face found in {image_path}")
                            continue
                        encodings.append(encoding)
                        names.append(person_name)
                    except Exception as exc:
                        self._log(f"[FACES] Failed to load {image_path}: {exc}")
            self.known_encodings = encodings
            self.known_names = names
            unique_people = sorted(set(names))
            if encodings:
                self._log(f"Loaded {len(encodings)} known faces: {unique_people}")
            else:
                self._log("[FACES] Warning: no known faces loaded")
            if not initial and RELOAD_FACES_FILE.exists():
                try:
                    RELOAD_FACES_FILE.unlink()
                except Exception:
                    pass

    def _capture_frame(self):
        if self.camera is None:
            return None
        try:
            frame = self.camera.capture_array()
            if frame is None:
                return None
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception as exc:
            self._log(f"[CAMERA] Capture failed: {exc}")
            return None

    def _read_motion(self):
        if not self.gpio_ready:
            return True
        try:
            return GPIO.input(PIR_PIN) == GPIO.HIGH
        except Exception as exc:
            self._log(f"[GPIO] PIR read failed: {exc}")
            return False

    def _set_leds(self, green=False, red=False, buzzer=False):
        if not self.gpio_ready:
            return
        try:
            GPIO.output(GREEN_LED_PIN, GPIO.HIGH if green else GPIO.LOW)
            GPIO.output(RED_LED_PIN, GPIO.HIGH if red else GPIO.LOW)
            GPIO.output(BUZZER_PIN, GPIO.HIGH if buzzer else GPIO.LOW)
        except Exception as exc:
            self._log(f"[GPIO] Output failed: {exc}")

    def _trigger_green(self):
        self._set_leds(green=True, red=False, buzzer=False)
        time.sleep(3)
        self._set_leds(green=False, red=False, buzzer=False)

    def _trigger_red_and_buzzer(self):
        self._set_leds(green=False, red=True, buzzer=False)
        for _ in range(3):
            self._set_leds(green=False, red=True, buzzer=True)
            time.sleep(0.5)
            self._set_leds(green=False, red=True, buzzer=False)
            time.sleep(0.5)
        time.sleep(2)
        self._set_leds(green=False, red=False, buzzer=False)

    def _build_caption(self, name: str, status: str, confidence: float, labels: list[str], timestamp_iso: str):
        labels_text = ", ".join(labels) if labels else "None"
        if status == "RECOGNISED":
            return (
                "✅ RECOGNISED PERSON DETECTED\n"
                f"Name: {name}\n"
                f"Confidence: {confidence:.1f}%\n"
                f"Time: {timestamp_iso}\n"
                f"Device: {DEVICE_ID}\n"
                f"Vision Labels: {labels_text}"
            )
        return (
            "🚨 UNKNOWN PERSON ALERT\n"
            f"Status: {status}\n"
            f"Time: {timestamp_iso}\n"
            f"Device: {DEVICE_ID}\n"
            "⚠️ Red LED and Buzzer triggered\n"
            f"Vision Labels: {labels_text}"
        )

    def _send_telegram_alert(self, caption: str, image_path: Path):
        if not self.telegram_enabled or self.telegram_bot is None or not image_path.exists():
            return False
        try:
            async def _send():
                with image_path.open("rb") as image_file:
                    await self.telegram_bot.send_photo(
                        chat_id=TELEGRAM_CHAT_ID,
                        photo=image_file,
                        caption=caption,
                    )

            asyncio.run(_send())
            return True
        except Exception as exc:
            self._log(f"[TELEGRAM] Send failed: {exc}")
            return False

    def _run_vision_labels(self, frame_bgr: np.ndarray):
        if not self.vision_ready or self.vision_client is None:
            return []
        try:
            ok, buffer = cv2.imencode(".jpg", frame_bgr)
            if not ok:
                return []
            image = vision.Image(content=buffer.tobytes())
            response = self.vision_client.label_detection(image=image)
            if response.label_annotations is None:
                return []
            return [label.description for label in response.label_annotations[:10]]
        except Exception as exc:
            self._log(f"[VISION] Label extraction failed: {exc}")
            return []

    def _save_event(self, payload: dict):
        if not self.firebase_ready or self.firebase_app is None:
            return False
        try:
            timestamp_ms = payload["timestamp_ms"]
            db.reference(f"recognitions/{DEVICE_ID}/{timestamp_ms}", app=self.firebase_app).set(payload)
            return True
        except Exception as exc:
            self._log(f"[FIREBASE] Write failed: {exc}")
            return False

    def _update_status(self, *, motion: bool, active: bool, seconds_remaining: int, last_event: dict | None = None):
        now = time.monotonic()
        if (now - self.last_status_write) < 0.25:
            return
        self.last_status_write = now
        status = {
            "device_id": DEVICE_ID,
            "camera": "ALWAYS ONLINE",
            "firebase": "Connected" if self.firebase_ready else "Disconnected",
            "vision_api": "Active" if self.vision_ready else "Inactive",
            "pir": "Motion" if motion else "Standby",
            "scan_active": bool(active),
            "seconds_remaining": int(max(0, seconds_remaining)),
            "countdown_label": (
                f"PIR: MOTION DETECTED — Scanning for {int(max(0, seconds_remaining))}s"
                if active and motion else
                (f"Scanning: {int(max(0, seconds_remaining))}s remaining" if active else "PIR: STANDBY")
            ),
            "last_motion": self._motion_timestamp(self.last_motion_wallclock) if self.last_motion_wallclock else None,
            "known_faces_count": len(self.known_encodings),
            "known_users": sorted(set(self.known_names)),
            "last_event": last_event,
            "timestamp": self._utc_now_iso(),
        }
        try:
            self._write_json(STATUS_FILE, status)
        except Exception as exc:
            self._log(f"[STATUS] Write failed: {exc}")

    @staticmethod
    def _utc_now_iso():
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _motion_timestamp(moment: float):
        if moment <= 0:
            return None
        return datetime.fromtimestamp(moment, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    def _process_frame(self, frame_bgr: np.ndarray):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(
            rgb,
            number_of_times_to_upsample=FACE_UPSAMPLE,
            model="hog",
        )
        encodings = face_recognition.face_encodings(rgb, locations)
        vision_labels = self._run_vision_labels(frame_bgr)
        annotated = frame_bgr.copy()
        event_payloads: list[dict] = []

        for location, encoding in zip(locations, encodings):
            top, right, bottom, left = location
            name = "Unknown"
            status = "UNKNOWN"
            confidence = 0.0
            color = (0, 0, 255)

            if self.known_encodings:
                matches = face_recognition.compare_faces(self.known_encodings, encoding, tolerance=FACE_TOLERANCE)
                distances = face_recognition.face_distance(self.known_encodings, encoding)
                if len(distances) and True in matches:
                    index = int(np.argmin(distances))
                    name = self.known_names[index]
                    status = "RECOGNISED"
                    confidence = max(0.0, (1.0 - float(distances[index])) * 100.0)
                    color = (0, 255, 0)

            cv2.rectangle(annotated, (left, top), (right, bottom), color, 2)
            label = name if status == "RECOGNISED" else "UNKNOWN"
            cv2.rectangle(annotated, (left, max(0, top - 28)), (right, top), color, cv2.FILLED)
            cv2.putText(
                annotated,
                label,
                (left + 6, max(16, top - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            timestamp_ms = int(time.time() * 1000)
            timestamp_iso = self._utc_now_iso()
            event = EventResult(
                name=name,
                status=status,
                confidence=round(confidence, 1),
                vision_labels=vision_labels,
                telegram_sent=False,
                timestamp_ms=timestamp_ms,
                timestamp_iso=timestamp_iso,
            )
            caption = self._build_caption(name, status, event.confidence, vision_labels, timestamp_iso)

            if status == "RECOGNISED":
                self._trigger_green()
            else:
                self._trigger_red_and_buzzer()

            telegram_sent = self._send_telegram_alert(caption, RAW_FRAME_FILE)
            event.telegram_sent = telegram_sent

            payload = {
                "deviceId": DEVICE_ID,
                "name": name,
                "status": status,
                "confidence": event.confidence,
                "vision_labels": vision_labels,
                "visionLabels": vision_labels,
                "telegram_sent": telegram_sent,
                "timestamp": timestamp_iso,
                "timestamp_ms": timestamp_ms,
                "frame": str(RAW_FRAME_FILE),
            }
            self._save_event(payload)
            event_payloads.append(payload)
            self.last_frame_result = payload

        if not locations:
            self.last_frame_result = {
                "deviceId": DEVICE_ID,
                "name": None,
                "status": "NO_FACE",
                "confidence": 0.0,
                "vision_labels": vision_labels,
                "telegram_sent": False,
                "timestamp": self._utc_now_iso(),
                "timestamp_ms": int(time.time() * 1000),
            }

        return annotated, event_payloads, vision_labels

    def _refresh_faces_if_requested(self):
        if RELOAD_FACES_FILE.exists():
            self._log("[FACES] Reload requested")
            self.reload_known_faces()

    def _scan_now_requested(self):
        if SCAN_NOW_FILE.exists():
            try:
                SCAN_NOW_FILE.unlink()
            except Exception:
                pass
            return True
        return False

    def run(self):
        self._log("Starting AI Surveillance System...")
        self._log(f"Device: {DEVICE_ID}")
        self._log(f"Faces directory: {FACES_DIR}")
        if not self.known_encodings:
            self._log("[FACES] Warning: 0 known faces loaded")
        self._set_leds(False, False, False)

        while True:
            self._refresh_faces_if_requested()

            motion = self._read_motion()
            manual_scan = self._scan_now_requested()
            if motion:
                self.last_motion_time = time.monotonic()
                self.last_motion_wallclock = time.time()
                self.scan_active_until = self.last_motion_time + SCAN_WINDOW_SECONDS
            elif manual_scan:
                self.scan_active_until = time.monotonic() + SCAN_WINDOW_SECONDS

            active = time.monotonic() < self.scan_active_until
            seconds_remaining = int(max(0, self.scan_active_until - time.monotonic())) if active else 0

            frame = self._capture_frame()
            if frame is None:
                self._update_status(motion=motion, active=active, seconds_remaining=seconds_remaining, last_event=self.last_frame_result)
                time.sleep(ACTIVE_SLEEP_SECONDS)
                continue

            self._save_frame(RAW_FRAME_FILE, frame)

            if active:
                annotated, events, labels = self._process_frame(frame)
                self._save_frame(ANNOTATED_FRAME_FILE, annotated)
                if events:
                    self._log(f"[SCAN] {len(events)} event(s) processed with labels: {labels}")
                self._update_status(motion=motion, active=True, seconds_remaining=seconds_remaining, last_event=self.last_frame_result)
                time.sleep(ACTIVE_SLEEP_SECONDS)
                continue

            self._save_frame(ANNOTATED_FRAME_FILE, frame)
            self._update_status(motion=motion, active=False, seconds_remaining=0, last_event=self.last_frame_result)
            time.sleep(IDLE_SLEEP_SECONDS)

    def cleanup(self):
        try:
            self._set_leds(False, False, False)
        except Exception:
            pass
        if self.camera is not None:
            try:
                self.camera.stop()
            except Exception:
                pass
        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
            except Exception:
                pass


def main():
    daemon = SurveillanceDaemon()
    try:
        daemon.run()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Keyboard interrupt received", flush=True)
    finally:
        daemon.cleanup()


if __name__ == "__main__":
    main()
