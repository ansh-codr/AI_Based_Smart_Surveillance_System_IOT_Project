import cv2

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None


class CameraService:
    def __init__(self, config, state, logger):
        self.config = config
        self.state = state
        self.logger = logger
        self.camera = None

    def init_camera(self):
        if self.camera is not None:
            return True

        if Picamera2 is None:
            self.state.update(camera_ready=False, camera_error="Picamera2 not installed")
            return False

        try:
            cam = Picamera2()
            cam.configure(
                cam.create_preview_configuration(
                    main={"format": "RGB888", "size": (640, 480)},
                    controls={"FrameRate": 15},
                )
            )
            cam.start()
            self.camera = cam
            self.state.update(camera_ready=True, camera_error=None)
            return True
        except Exception as exc:
            self.camera = None
            self.state.update(camera_ready=False, camera_error=str(exc))
            self.logger.exception("Camera init failed")
            return False

    def stop_camera(self):
        if self.camera is None:
            return
        try:
            self.camera.stop()
        except Exception:
            self.logger.exception("Camera stop failed")
        self.camera = None
        self.state.update(camera_ready=False)

    def capture_frame(self):
        if not self.init_camera():
            self.state.update(frame_error=self.state.snapshot()["camera_error"])
            return None

        try:
            frame = self.camera.capture_array()
        except Exception as exc:
            self.state.update(frame_error=str(exc), camera_error=str(exc))
            self.logger.exception("Camera capture failed")
            self.stop_camera()
            return None

        if frame is None:
            self.state.update(frame_error="Empty frame received")
            return None

        self.state.update(frame_error=None)
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
