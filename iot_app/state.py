from threading import Lock


class RuntimeState:
    def __init__(self):
        self.lock = Lock()
        self.intrusion_detected = False
        self.motion_detected = False
        self.camera_ready = False
        self.camera_error = None
        self.frame_error = None
        self.gpio_ready = False
        self.gpio_error = None

    def update(self, **kwargs):
        with self.lock:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def snapshot(self):
        with self.lock:
            return {
                "intrusion_detected": self.intrusion_detected,
                "motion_detected": self.motion_detected,
                "camera_ready": self.camera_ready,
                "camera_error": self.camera_error,
                "frame_error": self.frame_error,
                "gpio_ready": self.gpio_ready,
                "gpio_error": self.gpio_error,
            }
