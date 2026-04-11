# AI-Based Smart Surveillance System (IoT)

Flask-based smart surveillance application for Raspberry Pi with:
- Live MJPEG stream (`/video`)
- PIR-gated person detection (OpenCV HOG)
- GPIO alert outputs (LED + buzzer)
- Intruder snapshot capture
- Status endpoint (`/status`)

## Quick Start (Raspberry Pi)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:
- `http://<pi-ip>:5000/`
- `http://<pi-ip>:5000/status`
