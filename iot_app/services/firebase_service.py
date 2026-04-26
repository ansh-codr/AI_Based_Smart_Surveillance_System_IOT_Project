import os

try:
    import firebase_admin
    from firebase_admin import credentials
    from firebase_admin import firestore
    FIREBASE_AVAILABLE = True
except Exception:
    FIREBASE_AVAILABLE = False


class FirebaseService:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.db = None
        self._init_firebase()

    def _init_firebase(self):
        if not FIREBASE_AVAILABLE:
            self.logger.info("Firebase SDK not installed")
            return
        if not self.config.firebase_credentials:
            self.logger.info("Firebase credentials not configured")
            return
        if not os.path.exists(self.config.firebase_credentials):
            self.logger.warning("Firebase credentials file missing")
            return

        try:
            cred = credentials.Certificate(self.config.firebase_credentials)
            firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            self.logger.info("Firebase initialized")
        except Exception:
            self.logger.exception("Firebase init failed")

    def log_event(self, event):
        if self.db is None:
            return
        try:
            self.db.collection("events").add(event)
        except Exception:
            self.logger.exception("Firebase write failed")
