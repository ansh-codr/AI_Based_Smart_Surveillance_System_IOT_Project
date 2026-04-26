import os
import time
import cv2
import numpy as np


class MonitorService:
    def __init__(self, config, state, camera, gpio, detector, events, firebase, logger):
        self.config = config
        self.state = state
        self.camera = camera
        self.gpio = gpio
        self.detector = detector
        self.events = events
        self.firebase = firebase
        self.logger = logger
        self.last_snapshot_time = 0.0
        self.prev_motion = False
        self.prev_intrusion = False
        self.last_state = "idle"
        self.last_names = []

    def _save_intruder_snapshot(self, frame):
        now = time.monotonic()
        if (now - self.last_snapshot_time) < self.config.snapshot_cooldown_seconds:
            return
        os.makedirs(os.path.dirname(self.config.snapshot_path), exist_ok=True)
        cv2.imwrite(self.config.snapshot_path, frame)
        self.last_snapshot_time = now

    @staticmethod
    def _make_info_frame(width, height, text):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(
            frame,
            text,
            (30, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return frame

    @staticmethod
    def _encode_jpeg(frame, quality=75):
        ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), quality],
        )
        if not ok:
            return None
        return buffer.tobytes()

    @staticmethod
    def _multipart_frame(payload):
        return (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"
        )

    def _record_event(self, kind, detail):
        event = self.events.add_event(kind, detail)
        self.firebase.log_event(event)

    def _apply_state(self, state, names=None):
        if state == self.last_state:
            return

        if state == "recognized":
            self.gpio.set_alert_outputs(False)
            self.gpio.set_status_led(red_on=False, green_on=True)
            if names:
                self._record_event("recognized", "Recognized: " + ", ".join(names))
        elif state == "unknown":
            self.gpio.set_alert_outputs(True)
            self.gpio.set_status_led(red_on=True, green_on=False)
            self._record_event("intrusion", "Unknown face")
        elif state == "camera_error":
            self.gpio.set_alert_outputs(False)
            self.gpio.set_status_led(red_on=True, green_on=False)
        else:
            self.gpio.set_alert_outputs(False)
            self.gpio.set_status_led(red_on=False, green_on=False)

        self.last_state = state

    def stream_frames(self):
        frame_count = 0
        last_locations = []
        last_names = []
        idle_frame = self._make_info_frame(
            self.config.frame_width,
            self.config.frame_height,
            "No motion detected",
        )

        while True:
            motion = self.gpio.read_motion_sensor()
            self.state.update(motion_detected=motion)

            if motion and not self.prev_motion:
                self._record_event("motion", "Motion detected")
            if not motion and self.prev_motion:
                self._record_event("motion_clear", "Motion cleared")

            if not motion:
                last_locations = []
                last_names = []
                self.state.update(intrusion_detected=False)
                self._apply_state("idle")
                payload = self._encode_jpeg(idle_frame, quality=70)
                if payload is not None:
                    yield self._multipart_frame(payload)
                self.prev_motion = motion
                time.sleep(self.config.idle_sleep_seconds)
                continue

            frame = self.camera.capture_frame()
            if frame is None:
                self.state.update(intrusion_detected=False)
                self._apply_state("camera_error")
                text = "Camera unavailable: " + (
                    self.state.snapshot()["camera_error"]
                    or self.state.snapshot()["frame_error"]
                    or "unknown"
                )
                error_frame = self._make_info_frame(
                    self.config.frame_width,
                    self.config.frame_height,
                    text[:72],
                )
                payload = self._encode_jpeg(error_frame, quality=70)
                if payload is not None:
                    yield self._multipart_frame(payload)
                self.prev_motion = motion
                time.sleep(self.config.camera_retry_sleep_seconds)
                continue

            if frame_count % self.config.face_process_every_n_frames == 0:
                resize_factor = self.config.face_resize
                small = cv2.resize(frame, (0, 0), fx=resize_factor, fy=resize_factor)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                last_locations, last_names = self.detector.recognize(rgb_small)

            has_face = len(last_locations) > 0
            has_unknown = any(name == "Unknown" for name in last_names)
            has_recognized = any(name != "Unknown" for name in last_names)

            if not has_face:
                self.state.update(intrusion_detected=False)
                self._apply_state("idle")
            elif has_unknown:
                self.state.update(intrusion_detected=True)
                self._apply_state("unknown")
                self._save_intruder_snapshot(frame)
            elif has_recognized:
                self.state.update(intrusion_detected=False)
                self._apply_state("recognized", names=last_names)
            else:
                self.state.update(intrusion_detected=False)
                self._apply_state("idle")

            if last_locations:
                scale = 1.0 / self.config.face_resize
                for (top, right, bottom, left), name in zip(last_locations, last_names):
                    top = int(top * scale)
                    right = int(right * scale)
                    bottom = int(bottom * scale)
                    left = int(left * scale)
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(
                        frame,
                        name,
                        (left, max(top - 10, 0)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                        cv2.LINE_AA,
                    )
            frame_count += 1
            self.prev_motion = motion
            self.prev_intrusion = self.state.snapshot()["intrusion_detected"]

            payload = self._encode_jpeg(frame, quality=75)
            if payload is not None:
                yield self._multipart_frame(payload)

    def cleanup(self):
        self.gpio.set_alert_outputs(False)
        self.camera.stop_camera()
        self.gpio.cleanup()
