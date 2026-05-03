# Architecture

This document reflects the current code in the repository. GPIO defaults come from [iot_app/config.py](iot_app/config.py), web routes come from [iot_app/web/routes.py](iot_app/web/routes.py), and Firebase event writes come from [iot_app/services/firebase_service.py](iot_app/services/firebase_service.py).

## Runtime Topology

```text
PIR Sensor -> GPIO -> monitor.py -> Camera frame -> Face recognition -> GPIO alert
                                 \-> Vision API -> Firebase/Telegram

Flask app.py -> /dashboard, /api/* -> browser dashboard polling
```

## 9. Data Flow Summary Table

| Step | Component | Input | Output |
|------|-----------|-------|--------|
| 1 | PIR sensor | Motion | GPIO HIGH on pin 23 |
| 2 | root monitor.py | GPIO HIGH | Opens a 20-second active scan window |
| 3 | Picamera2 | Scan window active | RGB/BGR frame at 640x480 |
| 4 | face_recognition | Camera frame | Face locations and face encodings |
| 5 | compare_faces | Encodings | Recognised name or Unknown |
| 6 | gpio_service / GPIO control | Recognition result | Green LED, red LED, or buzzer state |
| 7 | Google Vision API | JPEG frame | Labels, objects, and face counts |
| 8 | firebase_service | Event data + labels | Firestore event document written |
| 9 | telegram_service | Alert result + photo | Telegram alert message sent |
| 10 | Flask `/api/frame` | HTTP request | Base64 JPEG frame JSON |
| 11 | Dashboard | Polling requests | Live UI refresh |

## 10. GPIO Pin Reference Table

| GPIO Pin | Component | Direction | Purpose |
|----------|-----------|-----------|---------|
| GPIO 23 | PIR sensor | INPUT | Motion detection |
| GPIO 17 | Green LED | OUTPUT | Recognised person indicator |
| GPIO 27 | Red LED | OUTPUT | Unknown person indicator |
| GPIO 22 | Buzzer | OUTPUT | Unknown alert sound |

## 11. API Endpoints Reference

| Method | Endpoint | Purpose | Poll Rate |
|--------|----------|---------|-----------|
| GET | `/` | Redirect to dashboard | On load |
| GET | `/dashboard` | Serve dashboard HTML | On load |
| GET | `/api/frame` | Base64 JPEG frame | Every 100ms |
| GET | `/status` | System status JSON | On load / manual refresh |
| GET | `/api/status` | System status JSON | Every 1s |
| GET | `/api/recognitions` | Last 20 recognition events | Every 3s |
| GET | `/events` | In-memory event list | On demand |
| GET | `/api/camera_status` | PIR countdown and camera state | Every 1s |
| POST | `/api/scan_now` | Trigger an immediate scan | On button click |
| POST | `/enroll` | Enroll a new face | On button click |
| GET | `/api/enrolled_users` | Known user list and count | On demand |
| POST | `/api/recognize_frame` | Device camera recognition | Every 2s |

## Firebase Data Model

The modular app writes plain event dictionaries into Firestore through [iot_app/services/firebase_service.py](iot_app/services/firebase_service.py). The event store used by the web app produces the same core shape:

| Field | Type | Source | Meaning |
|-------|------|--------|---------|
| kind | string | EventStore | Event category such as `motion`, `recognized`, or `intrusion` |
| detail | string | EventStore | Human-readable event description |
| timestamp | string | EventStore | UTC ISO-8601 timestamp ending in `Z` |

The root `monitor.py` daemon also writes recognition data to Firebase Realtime Database under `recognitions/<device_id>` for the `/api/recognitions` dashboard view. That RTDB path is separate from the Firestore writes performed by [iot_app/services/firebase_service.py](iot_app/services/firebase_service.py).
