import os

try:
    import face_recognition
    FACE_AVAILABLE = True
except Exception:
    FACE_AVAILABLE = False


class FaceRecognitionService:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.known_encodings = []
        self.known_names = []
        self.available = FACE_AVAILABLE
        self._load_known_faces()

    def _load_known_faces(self):
        if not self.available:
            self.logger.warning("face_recognition not available")
            return

        faces_dir = self.config.faces_dir
        if not os.path.isdir(faces_dir):
            self.logger.warning("Faces directory missing: %s", faces_dir)
            return

        for name in sorted(os.listdir(faces_dir)):
            path = os.path.join(faces_dir, name)
            if not os.path.isdir(path):
                continue
            for file_name in sorted(os.listdir(path)):
                if not file_name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                file_path = os.path.join(path, file_name)
                try:
                    image = face_recognition.load_image_file(file_path)
                    encodings = face_recognition.face_encodings(image)
                    if not encodings:
                        self.logger.warning("No face found in %s", file_path)
                        continue
                    self.known_encodings.append(encodings[0])
                    self.known_names.append(name)
                except Exception:
                    self.logger.exception("Failed to load face: %s", file_path)

        self.logger.info("Loaded %d face encodings", len(self.known_names))

    def reload(self):
        self.known_encodings = []
        self.known_names = []
        self._load_known_faces()

    def has_face(self, rgb_frame):
        if not self.available:
            return False
        locations = face_recognition.face_locations(rgb_frame)
        return bool(locations)

    def recognize(self, rgb_frame):
        if not self.available:
            return [], []

        locations = face_recognition.face_locations(rgb_frame)
        if not locations:
            return [], []

        encodings = face_recognition.face_encodings(rgb_frame, locations)
        names = []
        for encoding in encodings:
            matches = face_recognition.compare_faces(
                self.known_encodings,
                encoding,
                tolerance=self.config.face_tolerance,
            )
            name = "Unknown"
            if True in matches:
                first_match = matches.index(True)
                name = self.known_names[first_match]
            names.append(name)

        return locations, names
