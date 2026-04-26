from flask import Blueprint, Response, jsonify, render_template, request
from jinja2 import TemplateNotFound
import os
import time
import cv2


def create_blueprint(state, events, monitor, face_service):
    bp = Blueprint("web", __name__)

    @bp.route("/")
    def index():
        try:
            return render_template("index.html")
        except TemplateNotFound:
            return (
                "<h1>Smart Monitoring</h1>"
                "<p>System Active</p>"
                "<img src='/video' alt='Live video'>"
            )

    @bp.route("/video")
    def video():
        return Response(
            monitor.stream_frames(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @bp.route("/status")
    def status():
        return jsonify(state.snapshot())

    @bp.route("/events")
    def event_list():
        limit = request.args.get("limit", type=int)
        return jsonify({"events": events.get_events(limit)})

    @bp.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @bp.route("/enroll", methods=["POST"])
    def enroll():
        payload = request.get_json(silent=True) or {}
        name = (payload.get("name") or "").strip()
        if not name or not name.replace("_", "").replace("-", "").isalnum():
            return jsonify({"error": "Invalid name"}), 400

        if not face_service.available:
            return jsonify({"error": "face_recognition not available"}), 503

        frame = monitor.camera.capture_frame()
        if frame is None:
            return jsonify({"error": "Camera unavailable"}), 503

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if not face_service.has_face(rgb):
            return jsonify({"error": "No face detected"}), 422

        target_dir = os.path.join(monitor.config.faces_dir, name)
        os.makedirs(target_dir, exist_ok=True)
        filename = f"{int(time.time())}.jpg"
        file_path = os.path.join(target_dir, filename)
        cv2.imwrite(file_path, frame)

        face_service.reload()
        return jsonify({"message": "Face saved", "file": file_path})

    return bp
