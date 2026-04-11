# Architecture

- Flask routes provide dashboard, stream, and status APIs.
- Stream loop reads PIR motion state and gates detection.
- Picamera2 captures frames when motion is active.
- OpenCV HOG detector runs every N frames for CPU efficiency.
- GPIO drives LED and buzzer based on intrusion state.
- Intruder image saved as `intruder.jpg` with cooldown.
