from dataclasses import dataclass
import os


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class AppConfig:
    red_pin: int
    green_pin: int
    buzzer_pin: int
    pir_pin: int
    frame_width: int
    frame_height: int
    detect_width: int
    detect_height: int
    detect_every_n_frames: int
    face_process_every_n_frames: int
    face_tolerance: float
    face_resize: float
    faces_dir: str
    idle_sleep_seconds: float
    camera_retry_sleep_seconds: float
    snapshot_path: str
    snapshot_cooldown_seconds: float
    max_events: int
    firebase_credentials: str
    log_level: str
    log_file: str

    @staticmethod
    def from_env():
        return AppConfig(
            red_pin=_env_int("RED_PIN", 17),
            green_pin=_env_int("GREEN_PIN", 22),
            buzzer_pin=_env_int("BUZZER_PIN", 27),
            pir_pin=_env_int("PIR_PIN", 4),
            frame_width=_env_int("FRAME_WIDTH", 640),
            frame_height=_env_int("FRAME_HEIGHT", 480),
            detect_width=_env_int("DETECT_WIDTH", 320),
            detect_height=_env_int("DETECT_HEIGHT", 240),
            detect_every_n_frames=_env_int("DETECT_EVERY_N_FRAMES", 3),
            face_process_every_n_frames=_env_int("FACE_PROCESS_EVERY_N_FRAMES", 3),
            face_tolerance=_env_float("FACE_TOLERANCE", 0.45),
            face_resize=_env_float("FACE_RESIZE", 0.5),
            faces_dir=os.getenv("FACES_DIR", "faces"),
            idle_sleep_seconds=_env_float("IDLE_SLEEP_SECONDS", 0.1),
            camera_retry_sleep_seconds=_env_float("CAMERA_RETRY_SLEEP_SECONDS", 0.5),
            snapshot_path=os.getenv("SNAPSHOT_PATH", "data/intruder.jpg"),
            snapshot_cooldown_seconds=_env_float("SNAPSHOT_COOLDOWN_SECONDS", 4.0),
            max_events=_env_int("MAX_EVENTS", 50),
            firebase_credentials=os.getenv("FIREBASE_CREDENTIALS", ""),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", ""),
        )
