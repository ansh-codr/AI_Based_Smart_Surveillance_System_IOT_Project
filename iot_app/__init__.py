import atexit
from flask import Flask

from .config import AppConfig
from .logging_config import configure_logging
from .services.face_recognition_service import FaceRecognitionService
from .services.event_store import EventStore
from .services.firebase_service import FirebaseService
from .state import RuntimeState
from .web.routes import create_blueprint


def create_app():
    config = AppConfig.from_env()
    configure_logging(config)

    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")

    state = RuntimeState()
    detector = FaceRecognitionService(config, app.logger)
    events = EventStore(max_events=config.max_events)
    firebase = FirebaseService(config, app.logger)

    app.register_blueprint(create_blueprint(config, state, events, detector, firebase))

    atexit.register(firebase.cleanup)

    return app
