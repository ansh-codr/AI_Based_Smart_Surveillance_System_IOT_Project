import os
import time
import cv2
import numpy as np
from uuid import uuid4
from datetime import datetime

try:
    from google.cloud import vision
    VISION_AVAILABLE = True
except Exception:
    VISION_AVAILABLE = False

try:
    import firebase_admin
    from firebase_admin import storage
    FIREBASE_STORAGE_AVAILABLE = True
except Exception:
    FIREBASE_STORAGE_AVAILABLE = False


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
        self.last_cloud_trigger_time = 0.0
        self.last_motion_time = 0.0
        self.camera_active = False
        self.last_scan_time = 0.0
        self._vision_client = None

    @staticmethod
    def _now_string():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    def _trigger_cloud_enrichment(self, frame, reason, names=None):
        now = time.monotonic()
        if (now - self.last_cloud_trigger_time) < self.config.snapshot_cooldown_seconds:
            return

        payload = self._encode_jpeg(frame, quality=80)
        if payload is None:
            return

        vision_result = self._run_vision_api(payload)

        metadata = {
            "triggerReason": reason,
            "localNames": ",".join(names or []),
            "localDecision": "unknown" if reason == "unknown" else "motion",
            "eventTs": str(int(time.time())),
        }

        if vision_result:
            metadata.update({
                "visionLabels": vision_result.get("labels", []),
                "visionObjects": vision_result.get("objects", []),
                "visionFacesCount": str(vision_result.get("facesCount", 0)),
                "personDetected": str(vision_result.get("personDetected", False)),
            })

        try:
            ref = None
            if hasattr(self.firebase, "db") and self.firebase.db is not None:
                ref = self.firebase.db.collection("events")
            elif FIREBASE_STORAGE_AVAILABLE:
                bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
                device_id = os.getenv("DEVICE_ID", "pi-device").strip() or "pi-device"
                if bucket_name:
                    firebase_admin.get_app()
                    frame_id = f"{int(time.time())}_{uuid4().hex[:8]}"
                    blob_path = f"frames/{device_id}/{frame_id}.jpg"
                    blob = storage.bucket(bucket_name).blob(blob_path)
                    blob.metadata = metadata
                    blob.upload_from_string(payload, content_type="image/jpeg")
            self.last_cloud_trigger_time = now
        except Exception:
            # Cloud errors must never interrupt local monitoring.
            self.logger.exception("Cloud enrichment trigger failed")

    def _run_vision_api(self, payload):
        if not VISION_AVAILABLE:
            return None
        try:
            if self._vision_client is None:
                self._vision_client = vision.ImageAnnotatorClient()
            image = vision.Image(content=payload)
            response = self._vision_client.annotate_image({
                "image": image,
                "features": [
                    {"type_": vision.Feature.Type.LABEL_DETECTION, "max_results": 10},
                    {"type_": vision.Feature.Type.FACE_DETECTION, "max_results": 10},
                    {"type_": vision.Feature.Type.OBJECT_LOCALIZATION, "max_results": 10},
                ],
            })
            if response.error.message:
                return None

            labels = [
                {"description": item.description, "score": float(item.score)}
                for item in response.label_annotations
            ]
            objects = [
                {"name": item.name, "score": float(item.score)}
                for item in response.localized_object_annotations
            ]
            faces_count = len(response.face_annotations)
            person_detected = any(
                "person" in item["description"].lower() or "human" in item["description"].lower()
                for item in labels
            ) or any(
                "person" in item["name"].lower() or "human" in item["name"].lower()
                for item in objects
            ) or faces_count > 0
            return {
                "labels": labels,
                "objects": objects,
                "facesCount": faces_count,
                "personDetected": person_detected,
            }
        except Exception:
            self.logger.exception("Vision API extraction failed")
            return None

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

    def _update_camera_status(self, active, seconds_remaining=0):
        self.state.update(
            camera_active=active,
            seconds_remaining=max(0, int(seconds_remaining)),
            last_motion=self._now_string() if self.last_motion_time else None,
        )

    def stream_frames(self):
        frame_count = 0
        last_locations = []
        last_names = []
        idle_frame = self._make_info_frame(
            self.config.frame_width,
            self.config.frame_height,
            "STANDBY - waiting for motion",
        )

        while True:
            motion = self.gpio.read_motion_sensor()
            self.state.update(motion_detected=motion)
            current_time = time.monotonic()

            if motion:
                self.last_motion_time = current_time
                if not self.camera_active:
                    self.logger.info("Motion detected - camera activated for %ss", 20)
                    self._record_event("motion", "Motion detected")
                    self.camera_active = True
            elif self.prev_motion:
                self._record_event("motion_clear", "Motion cleared")

            if not self.camera_active:
                last_locations = []
                last_names = []
                self.state.update(intrusion_detected=False)
                self._apply_state("idle")
                self._update_camera_status(False, 0)
                payload = self._encode_jpeg(idle_frame, quality=70)
                if payload is not None:
                    yield self._multipart_frame(payload)
                self.prev_motion = motion
                time.sleep(self.config.idle_sleep_seconds)
                continue

            elapsed = current_time - self.last_motion_time
            if elapsed >= 20:
                self.logger.info("No motion for 20s - camera standby")
                self.camera_active = False
                self._update_camera_status(False, 0)
                self.state.update(intrusion_detected=False)
                self._apply_state("idle")
                standby_frame = self._make_info_frame(
                    self.config.frame_width,
                    self.config.frame_height,
                    "STANDBY - waiting for motion",
                )
                payload = self._encode_jpeg(standby_frame, quality=70)
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

            summary = self.detector.summarize_results(last_locations, last_names)
            has_face = summary["has_face"]
            has_unknown = summary["has_unknown"]
            has_recognized = summary["has_recognized"]
            recognized_names = summary["recognized_names"]

            if (current_time - self.last_scan_time) >= 2:
                self.last_scan_time = current_time
                self.logger.info("Scanning... (%ss remaining)", int(max(0, 20 - elapsed)))

            if motion and not self.prev_motion:
                self._trigger_cloud_enrichment(frame, reason="motion", names=recognized_names)

            if not has_face:
                self.state.update(intrusion_detected=False)
                self._apply_state("idle")
            elif has_unknown:
                self.state.update(intrusion_detected=True)
                self._apply_state("unknown")
                self._save_intruder_snapshot(frame)
                if not self.prev_intrusion:
                    self._trigger_cloud_enrichment(
                        frame,
                        reason="unknown",
                        names=recognized_names,
                    )
            elif has_recognized:
                self.state.update(intrusion_detected=False)
                self._apply_state("recognized", names=recognized_names)
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
                    color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.putText(
                        frame,
                        name,
                        (left, max(top - 10, 0)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2,
                        cv2.LINE_AA,
                    )
            frame_count += 1
            self.prev_motion = motion
            self.prev_intrusion = self.state.snapshot()["intrusion_detected"]
            self._update_camera_status(True, 20 - elapsed)

            payload = self._encode_jpeg(frame, quality=75)
            if payload is not None:
                yield self._multipart_frame(payload)

    def cleanup(self):
        self.gpio.set_alert_outputs(False)
        self.camera.stop_camera()
        self.gpio.cleanup()
