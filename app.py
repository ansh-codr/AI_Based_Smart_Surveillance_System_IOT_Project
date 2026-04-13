import glob
import os
import time
from datetime import datetime
from threading import Lock
from urllib import parse, request

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template
from jinja2 import TemplateNotFound

try:
    import face_recognition
except Exception:
    face_recognition = None

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None

try:
    import RPi.GPIO as GPIO
    GPIO_IMPORT_OK = True
except Exception:
    GPIO_IMPORT_OK = False

    class _MockGPIO:
        BCM = "BCM"
        OUT = "OUT"
        IN = "IN"
        LOW = 0
        HIGH = 1

        @staticmethod
        def setmode(_mode):
            return None

        @staticmethod
        def setup(_pin, _mode, initial=None):
            return None

        @staticmethod
        def input(_pin):
            return 1

        @staticmethod
        def output(_pin, _value):
            return None

        @staticmethod
        def cleanup():
            return None

    GPIO = _MockGPIO()


# GPIO pins
PIR_PIN = 4
LED_PIN = 17
BUZZER_PIN = 27

# Performance tuning for Raspberry Pi 4
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
DETECT_WIDTH = 320
DETECT_HEIGHT = 240
DETECT_EVERY_N_FRAMES = 3
FACE_EVERY_N_FRAMES = 4
IDLE_SLEEP_SECONDS = 0.12
CAMERA_RETRY_SLEEP_SECONDS = 0.5
INTRUSION_ALERT_COOLDOWN_SECONDS = 12
INTRUDER_SAVE_COOLDOWN_SECONDS = 4

DATASET_DIR = "dataset"
CAPTURE_DIR = os.path.join("static", "captures")

# Optional mobile alert config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()

app = Flask(__name__)

# Runtime state
camera = None
camera_error = None
frame_error = None
gpio_error = None
gpio_ready = False
dataset_error = None

known_face_encodings = []
known_face_names = []

status_lock = Lock()
intrusion_detected = False
motion_detected = False
status_text = "No Motion"
last_capture_file = None
last_intrusion_alert_time = 0.0
last_intruder_save_time = 0.0

# Lightweight person detector
hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


# ------------------------------
# GPIO control
# ------------------------------
def init_gpio():
    global gpio_ready, gpio_error
    if not GPIO_IMPORT_OK:
        gpio_ready = False
        gpio_error = "RPi.GPIO not installed"
        return False

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LED_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(PIR_PIN, GPIO.IN)
        gpio_ready = True
        gpio_error = None
        return True
    except Exception as exc:
        gpio_ready = False
        gpio_error = str(exc)
        return False


def set_alert_outputs(active):
    if not gpio_ready:
        return
    state = GPIO.HIGH if active else GPIO.LOW
    try:
        GPIO.output(LED_PIN, state)
        GPIO.output(BUZZER_PIN, state)
    except Exception:
        pass


def read_motion_sensor():
    if not gpio_ready:
        # Degrade gracefully in dev environments with no GPIO/PIR.
        return True
    try:
        return GPIO.input(PIR_PIN) == GPIO.HIGH
    except Exception:
        return False


# ------------------------------
# Camera handling
# ------------------------------
def init_camera():
    global camera, camera_error
    if camera is not None:
        return True

    if Picamera2 is None:
        camera_error = "Picamera2 is not installed"
        return False

    try:
        cam = Picamera2()
        config = cam.create_video_configuration(main={"size": (FRAME_WIDTH, FRAME_HEIGHT)})
        cam.configure(config)
        cam.start()
        camera = cam
        camera_error = None
        return True
    except Exception as exc:
        camera = None
        camera_error = str(exc)
        return False


def stop_camera():
    global camera
    if camera is None:
        return
    try:
        camera.stop()
    except Exception:
        pass
    camera = None


def capture_camera_frame():
    global frame_error, camera_error

    if not init_camera():
        frame_error = camera_error
        return None

    try:
        frame = camera.capture_array()
    except Exception as exc:
        frame_error = str(exc)
        camera_error = frame_error
        stop_camera()
        return None

    if frame is None:
        frame_error = "Frame read failure"
        return None

    frame_error = None
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


# ------------------------------
# AI detection and recognition
# ------------------------------
def detect_people(frame):
    small = cv2.resize(frame, (DETECT_WIDTH, DETECT_HEIGHT))
    boxes, _weights = hog.detectMultiScale(
        small,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.08,
    )
    return boxes


def scale_person_boxes(boxes, frame):
    scaled = []
    sx = frame.shape[1] / float(DETECT_WIDTH)
    sy = frame.shape[0] / float(DETECT_HEIGHT)
    for x, y, w, h in boxes:
        x1 = int(x * sx)
        y1 = int(y * sy)
        x2 = int((x + w) * sx)
        y2 = int((y + h) * sy)
        scaled.append((x1, y1, x2, y2))
    return scaled


def load_known_faces(dataset_root=DATASET_DIR):
    global known_face_encodings, known_face_names, dataset_error
    known_face_encodings = []
    known_face_names = []

    if face_recognition is None:
        dataset_error = "face_recognition is not installed"
        return 0

    if not os.path.isdir(dataset_root):
        dataset_error = f"Dataset folder missing: {dataset_root}"
        return 0

    person_dirs = [d for d in sorted(os.listdir(dataset_root)) if os.path.isdir(os.path.join(dataset_root, d))]
    if not person_dirs:
        dataset_error = "Dataset is empty"
        return 0

    for person_name in person_dirs:
        person_path = os.path.join(dataset_root, person_name)
        for image_path in sorted(glob.glob(os.path.join(person_path, "*"))):
            if not os.path.isfile(image_path):
                continue
            try:
                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)
            except Exception:
                continue

            if not encodings:
                continue

            known_face_encodings.append(encodings[0])
            known_face_names.append(person_name)

    if not known_face_encodings:
        dataset_error = "No valid face encodings found in dataset"
        return 0

    dataset_error = None
    return len(known_face_encodings)


def recognize_faces(frame):
    if face_recognition is None:
        return [], []

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locations = face_recognition.face_locations(rgb, model="hog")
    if not locations:
        return [], []

    encodings = face_recognition.face_encodings(rgb, locations)
    labels = []

    for encoding in encodings:
        label = "Intruder"
        if known_face_encodings:
            matches = face_recognition.compare_faces(known_face_encodings, encoding, tolerance=0.5)
            distances = face_recognition.face_distance(known_face_encodings, encoding)
            if len(distances) > 0:
                best_index = int(np.argmin(distances))
                if matches[best_index]:
                    label = known_face_names[best_index]
        labels.append(label)

    return locations, labels


def draw_annotations(frame, person_boxes, face_locations, face_labels):
    for x1, y1, x2, y2 in person_boxes:
        cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 220, 40), 2)
        cv2.putText(
            frame,
            "Person",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (40, 220, 40),
            2,
            cv2.LINE_AA,
        )

    for (top, right, bottom, left), name in zip(face_locations, face_labels):
        is_intruder = name == "Intruder"
        color = (20, 20, 230) if is_intruder else (230, 180, 20)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(
            frame,
            name,
            (left, max(20, top - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )


# ------------------------------
# Alerts and capture storage
# ------------------------------
def ensure_capture_dir():
    os.makedirs(CAPTURE_DIR, exist_ok=True)


def save_intruder_snapshot(frame):
    global last_capture_file, last_intruder_save_time

    now = time.monotonic()
    if (now - last_intruder_save_time) < INTRUDER_SAVE_COOLDOWN_SECONDS:
        return None

    ensure_capture_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"intruder_{ts}.jpg"
    full_path = os.path.join(CAPTURE_DIR, filename)
    ok = cv2.imwrite(full_path, frame)
    if not ok:
        return None

    last_capture_file = filename
    last_intruder_save_time = now
    return full_path


def send_mobile_alert(message, image_path=None):
    global last_intrusion_alert_time
    now = time.monotonic()
    if (now - last_intrusion_alert_time) < INTRUSION_ALERT_COOLDOWN_SECONDS:
        return

    # Telegram text alert
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
            data = parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
            req = request.Request(f"{base}/sendMessage", data=data, method="POST")
            with request.urlopen(req, timeout=6):
                pass
        except Exception:
            pass

        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, "rb") as fh:
                    photo_bytes = fh.read()
                boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                body = []
                body.append(f"--{boundary}".encode())
                body.append(b'Content-Disposition: form-data; name="chat_id"\r\n')
                body.append(TELEGRAM_CHAT_ID.encode())
                body.append(f"--{boundary}".encode())
                body.append(
                    b'Content-Disposition: form-data; name="photo"; filename="intruder.jpg"\r\n'
                    b"Content-Type: image/jpeg\r\n"
                )
                body.append(photo_bytes)
                body.append(f"--{boundary}--".encode())
                payload = b"\r\n".join(body)
                req = request.Request(
                    f"{base}/sendPhoto",
                    data=payload,
                    method="POST",
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                )
                with request.urlopen(req, timeout=8):
                    pass
            except Exception:
                pass

    # Generic HTTP webhook alert
    if ALERT_WEBHOOK_URL:
        try:
            payload = parse.urlencode({"message": message, "image": image_path or ""}).encode("utf-8")
            req = request.Request(ALERT_WEBHOOK_URL, data=payload, method="POST")
            with request.urlopen(req, timeout=6):
                pass
        except Exception:
            pass

    last_intrusion_alert_time = now


# ------------------------------
# Streaming helpers
# ------------------------------
def make_info_frame(text):
    frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.putText(
        frame,
        text,
        (24, FRAME_HEIGHT // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame


def encode_jpeg(frame, quality=74):
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return None
    return buffer.tobytes()


def multipart_frame(payload):
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"


# ------------------------------
# Main processing pipeline
# ------------------------------
def stream_frames():
    global intrusion_detected, motion_detected, status_text

    frame_count = 0
    last_person_boxes = []
    last_face_locations = []
    last_face_labels = []

    while True:
        motion = read_motion_sensor()
        with status_lock:
            motion_detected = motion

        if not motion:
            with status_lock:
                intrusion_detected = False
                status_text = "No Motion"
            set_alert_outputs(False)
            info = make_info_frame("No Motion")
            payload = encode_jpeg(info, quality=70)
            if payload:
                yield multipart_frame(payload)
            time.sleep(IDLE_SLEEP_SECONDS)
            continue

        frame = capture_camera_frame()
        if frame is None:
            with status_lock:
                intrusion_detected = False
                status_text = "No Motion"
            set_alert_outputs(False)
            text = f"Camera Error: {camera_error or frame_error or 'unknown'}"
            info = make_info_frame(text[:72])
            payload = encode_jpeg(info, quality=70)
            if payload:
                yield multipart_frame(payload)
            time.sleep(CAMERA_RETRY_SLEEP_SECONDS)
            continue

        if frame_count % DETECT_EVERY_N_FRAMES == 0:
            detected = detect_people(frame)
            last_person_boxes = scale_person_boxes(detected, frame)

        has_person = len(last_person_boxes) > 0

        if has_person and frame_count % FACE_EVERY_N_FRAMES == 0:
            last_face_locations, last_face_labels = recognize_faces(frame)
        elif not has_person:
            last_face_locations, last_face_labels = [], []

        has_intruder = has_person and any(name == "Intruder" for name in last_face_labels)
        # If a person is detected but no face is detected, fail-safe as intruder.
        if has_person and len(last_face_labels) == 0:
            has_intruder = True

        if has_intruder:
            set_alert_outputs(True)
            image_path = save_intruder_snapshot(frame)
            send_mobile_alert("Intruder detected by Raspberry Pi surveillance system", image_path)
            with status_lock:
                intrusion_detected = True
                status_text = "Intruder Detected"
        else:
            set_alert_outputs(False)
            with status_lock:
                intrusion_detected = False
                status_text = "Motion Detected" if has_person else "No Motion"

        draw_annotations(frame, last_person_boxes, last_face_locations, last_face_labels)
        frame_count += 1

        payload = encode_jpeg(frame, quality=74)
        if payload:
            yield multipart_frame(payload)


# ------------------------------
# Flask routes
# ------------------------------
@app.route("/")
def index():
    try:
        return render_template("index.html")
    except TemplateNotFound:
        return (
            "<h1>Smart Surveillance System</h1>"
            "<p id='status'>No Motion</p>"
            "<img src='/video_feed' alt='Live video feed' style='width:640px;'>"
        )


@app.route("/video_feed")
def video_feed():
    return Response(stream_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video")
def video_compat():
    return Response(stream_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/status")
def status():
    with status_lock:
        state = {
            "status_text": status_text,
            "intrusion_detected": intrusion_detected,
            "motion_detected": motion_detected,
        }

    state.update(
        {
            "camera_ready": camera is not None,
            "camera_error": camera_error,
            "frame_error": frame_error,
            "gpio_ready": gpio_ready,
            "gpio_error": gpio_error,
            "dataset_error": dataset_error,
            "known_faces": len(known_face_encodings),
            "last_image": f"/static/captures/{last_capture_file}" if last_capture_file else None,
            "pir_pin": PIR_PIN,
            "led_pin": LED_PIN,
            "buzzer_pin": BUZZER_PIN,
            "resolution": f"{FRAME_WIDTH}x{FRAME_HEIGHT}",
        }
    )
    return jsonify(state)


def cleanup_resources():
    set_alert_outputs(False)
    stop_camera()
    try:
        GPIO.cleanup()
    except Exception:
        pass


if __name__ == "__main__":
    ensure_capture_dir()
    init_gpio()
    load_known_faces(DATASET_DIR)
    init_camera()
    try:
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
    finally:
        cleanup_resources()
