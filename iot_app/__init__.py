import atexit
from flask import Flask

from .config import AppConfig
from .logging_config import configure_logging
from .monitor import MonitorService
from .services.camera_service import CameraService
from .services.face_recognition_service import FaceRecognitionService
from .services.event_store import EventStore
from .services.firebase_service import FirebaseService
from .services.gpio_service import GPIOService
from .state import RuntimeState
from .web.routes import create_blueprint


def create_app():
    config = AppConfig.from_env()
    configure_logging(config)

    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")

    state = RuntimeState()
    gpio = GPIOService(config, state, app.logger)
    camera = CameraService(config, state, app.logger)
    detector = FaceRecognitionService(config, app.logger)
    events = EventStore(max_events=config.max_events)
    firebase = FirebaseService(config, app.logger)
    monitor = MonitorService(config, state, camera, gpio, detector, events, firebase, app.logger)

    gpio.init_gpio()

    app.register_blueprint(create_blueprint(state, events, monitor, detector))

    atexit.register(monitor.cleanup)

    return app
