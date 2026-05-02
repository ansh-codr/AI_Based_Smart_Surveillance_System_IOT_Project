import os

import numpy as np

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

        for root, _dirs, files in os.walk(faces_dir):
            for file_name in sorted(files):
                if not file_name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                file_path = os.path.join(root, file_name)
                person = os.path.basename(root)
                try:
                    image = face_recognition.load_image_file(file_path)
                    encodings = face_recognition.face_encodings(image)
                    if not encodings:
                        self.logger.warning("No face found in %s", file_path)
                        continue
                    self.known_encodings.append(encodings[0])
                    self.known_names.append(person)
                except Exception:
                    self.logger.exception("Failed to load face: %s", file_path)

        self.logger.info("Loaded %d known faces: %s", len(self.known_names), sorted(set(self.known_names)))

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

        locations = face_recognition.face_locations(
            rgb_frame,
            number_of_times_to_upsample=2,
            model="hog",
        )
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
            distances = face_recognition.face_distance(self.known_encodings, encoding) if self.known_encodings else []
            name = "Unknown"
            if True in matches and len(distances) > 0:
                first_match = int(np.argmin(distances))
                name = self.known_names[first_match]
            names.append(name)

        return locations, names

    @staticmethod
    def summarize_results(locations, names):
        has_face = len(locations) > 0
        known_names = [name for name in names if name != "Unknown"]
        unknown_count = sum(1 for name in names if name == "Unknown")
        return {
            "has_face": has_face,
            "has_unknown": unknown_count > 0,
            "has_recognized": len(known_names) > 0,
            "recognized_names": sorted(set(known_names)),
            "unknown_count": unknown_count,
        }
