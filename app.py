from flask import Flask, Response, jsonify, render_template
import cv2
from jinja2 import TemplateNotFound
from threading import Lock
import time

import numpy as np

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


LED_PIN = 17
BUZZER_PIN = 27
PIR_PIN = 4

FRAME_WIDTH = 640
FRAME_HEIGHT = 480
DETECT_WIDTH = 320
DETECT_HEIGHT = 240
DETECT_EVERY_N_FRAMES = 3
IDLE_SLEEP_SECONDS = 0.1
CAMERA_RETRY_SLEEP_SECONDS = 0.5
INTRUDER_SNAPSHOT_PATH = "intruder.jpg"
INTRUDER_SNAPSHOT_COOLDOWN_SECONDS = 4

app = Flask(__name__)

# Runtime state
camera = None
camera_error = None
frame_error = None
gpio_error = None
gpio_ready = False

intrusion_detected = False
motion_detected = False
last_snapshot_time = 0.0

status_lock = Lock()

# Lightweight default person detector
hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


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
        # Keep stream alive even if GPIO write fails.
        pass


def read_motion_sensor():
    if not gpio_ready:
        # If PIR is unavailable, keep feature functional by processing frames.
        return True
    try:
        return GPIO.input(PIR_PIN) == GPIO.HIGH
    except Exception:
        return False


def init_camera():
    global camera, camera_error

    if camera is not None:
        return True

    if Picamera2 is None:
        camera_error = "Picamera2 is not installed in this environment"
        return False

    try:
        cam = Picamera2()
        cam.configure(
            cam.create_video_configuration(main={"size": (FRAME_WIDTH, FRAME_HEIGHT)})
        )
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
        frame_error = "Empty frame received"
        return None

    frame_error = None
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)


def detect_people(frame):
    small = cv2.resize(frame, (DETECT_WIDTH, DETECT_HEIGHT))
    boxes, _weights = hog.detectMultiScale(
        small,
        winStride=(8, 8),
        padding=(8, 8),
        scale=1.08,
    )
    return boxes


def draw_person_boxes(frame, boxes):
    scale_x = frame.shape[1] / float(DETECT_WIDTH)
    scale_y = frame.shape[0] / float(DETECT_HEIGHT)
    for x, y, w, h in boxes:
        x1 = int(x * scale_x)
        y1 = int(y * scale_y)
        x2 = int((x + w) * scale_x)
        y2 = int((y + h) * scale_y)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)


def save_intruder_snapshot(frame):
    global last_snapshot_time

    now = time.monotonic()
    if (now - last_snapshot_time) < INTRUDER_SNAPSHOT_COOLDOWN_SECONDS:
        return
    cv2.imwrite(INTRUDER_SNAPSHOT_PATH, frame)
    last_snapshot_time = now


def make_info_frame(text):
    frame = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.putText(
        frame,
        text,
        (30, FRAME_HEIGHT // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame


def encode_jpeg(frame, quality=75):
    ok, buffer = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), quality],
    )
    if not ok:
        return None
    return buffer.tobytes()


def multipart_frame(payload):
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"
    )


def stream_frames():
    global intrusion_detected, motion_detected

    frame_count = 0
    last_boxes = []
    idle_frame = make_info_frame("No motion detected")

    while True:
        motion = read_motion_sensor()
        with status_lock:
            motion_detected = motion

        if not motion:
            last_boxes = []
            with status_lock:
                intrusion_detected = False
            set_alert_outputs(False)
            payload = encode_jpeg(idle_frame, quality=70)
            if payload is not None:
                yield multipart_frame(payload)
            time.sleep(IDLE_SLEEP_SECONDS)
            continue

        frame = capture_camera_frame()
        if frame is None:
            with status_lock:
                intrusion_detected = False
            set_alert_outputs(False)
            text = f"Camera unavailable: {camera_error or frame_error or 'unknown'}"
            error_frame = make_info_frame(text[:72])
            payload = encode_jpeg(error_frame, quality=70)
            if payload is not None:
                yield multipart_frame(payload)
            time.sleep(CAMERA_RETRY_SLEEP_SECONDS)
            continue

        if frame_count % DETECT_EVERY_N_FRAMES == 0:
            last_boxes = detect_people(frame)

        has_person = len(last_boxes) > 0
        with status_lock:
            intrusion_detected = has_person

        if has_person:
            set_alert_outputs(True)
            save_intruder_snapshot(frame)
        else:
            set_alert_outputs(False)

        draw_person_boxes(frame, last_boxes)
        frame_count += 1

        payload = encode_jpeg(frame, quality=75)
        if payload is not None:
            yield multipart_frame(payload)


@app.route("/")
def index():
    try:
        return render_template("index.html")
    except TemplateNotFound:
        return (
            "<h1>Smart Surveillance System</h1>"
            "<p>System Active</p>"
            "<img src='/video' alt='Live video'>"
        )


@app.route("/video")
def video():
    return Response(
        stream_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/status")
def status():
    with status_lock:
        detected = intrusion_detected
        motion = motion_detected

    return jsonify(
        {
            "intrusion_detected": detected,
            "motion_detected": motion,
            "camera_ready": camera is not None,
            "camera_error": camera_error,
            "frame_error": frame_error,
            "gpio_ready": gpio_ready,
            "gpio_error": gpio_error,
        }
    )


def cleanup_resources():
    set_alert_outputs(False)
    stop_camera()
    try:
        GPIO.cleanup()
    except Exception:
        pass


if __name__ == "__main__":
    init_gpio()
    init_camera()
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        cleanup_resources()
