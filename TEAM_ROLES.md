# AI Surveillance System — Team Responsibility Document

## Project Overview (2 paragraphs)
This project is an AI-enabled Raspberry Pi surveillance platform that runs an always-on camera feed, detects motion through a PIR sensor, and executes a 20-second active scanning window whenever motion is detected. During active windows, the system performs local face recognition, overlays recognition results on frames, updates hardware indicators (green LED for recognised, red LED + buzzer for unknown), and stores recognition events with timestamps and labels.

The software stack combines a hardware daemon (`monitor.py`) and a Flask web/API layer (`app.py` + `iot_app`). The daemon owns camera and GPIO, while the dashboard and APIs consume shared status/frame artifacts from `/tmp` and Firebase. Cloud integration includes Firebase Realtime Database logging, optional Firebase Cloud Functions for storage-triggered analysis, Google Vision labeling, and Telegram alert delivery with captured images.

## System Architecture Diagram (ASCII art showing all components)
```
+------------------------- Raspberry Pi Device -------------------------+
|                                                                       |
|  +---------------------+         +-------------------------------+    |
|  | monitor.py daemon   |         | Flask App (app.py + iot_app) |    |
|  |---------------------|         |-------------------------------|    |
|  | Picamera2 capture   |         | /dashboard, /api/status       |    |
|  | PIR scan loop       |         | /api/recognitions, /enroll    |    |
|  | face_recognition    |         | /video_feed (MJPEG)           |    |
|  | GPIO LEDs + buzzer  |         |                               |    |
|  +----------+----------+         +---------------+---------------+    |
|             |                                    |                    |
|             v                                    v                    |
|      /tmp/iot_status.json                dashboard.html + JS polling  |
|      /tmp/iot_latest_raw.jpg             (refreshStatus/refreshAlerts)|
|      /tmp/iot_latest_annotated.jpg                                 |
|                                                                       |
+-------------+----------------------+----------------------+------------+
              |                      |                      |
              v                      v                      v
     Firebase RTDB           Google Vision API         Telegram Bot API
 (recognitions/device/ts)   (label_detection)      (photo + alert caption)
              |
              v
   Cloud Function (index.js)
   trigger: Storage frames/* uploads
```

## Role Summary Table
| Role | Title | Files Owned | Hardware | People |
|------|-------|-------------|----------|--------|
| Role 1 | Edge Hardware Control & Motion Safety | `monitor.py`, `iot_app/services/gpio_service.py`, `iot_app/config.py`, `iot_app/state.py` | PIR, LEDs, buzzer, GPIO | Person A, Person B |
| Role 2 | Camera & Stream Pipeline | `monitor.py`, `iot_app/services/camera_service.py`, `iot_app/web/routes.py`, `app.py` | Pi Camera module, CSI link, Pi board | Person A, Person B |
| Role 3 | Face Recognition & Enrollment | `monitor.py`, `iot_app/services/face_recognition_service.py`, `iot_app/web/routes.py`, `README.md` | Camera framing for enrollment and recognition | Person A, Person B |
| Role 4 | Firebase + Cloud Functions | `monitor.py`, `iot_app/services/firebase_service.py`, `iot_app/web/routes.py`, `cloud-functions/functions/index.js` | Pi as cloud event source | Person A, Person B |
| Role 5 | Telegram Bot + Vision API | `monitor.py`, `iot_app/services/telegram_service.py`, `requirements.txt`, `README.md` | Camera snapshot source, alert workflow hardware context | Person A, Person B |
| Role 6 | Dashboard UX + Deployment | `dashboard.html`, `iot_app/web/routes.py`, `iot_app/__init__.py`, `app.py`, `start.sh`, `requirements.txt`, `README.md` | Host Raspberry Pi, LAN client devices | Person A, Person B |

---

## ROLE 1 — Edge Hardware Control & Motion Safety
### Assigned To
Person A | Person B

### Overview
This role owns the physical safety loop that decides when the system scans and how local alerts are actuated. They handle PIR input, GPIO setup, LED/buzzer outputs, active-window timing, and safe hardware cleanup. They also verify that the runtime state model reflects real hardware conditions and errors.

### Files & Line Ownership
| File | Lines | Responsibility |
|------|-------|----------------|
| /home/pi/Desktop/IOT/monitor.py | 24-29 | GPIO import availability and fallback mode decision |
| /home/pi/Desktop/IOT/monitor.py | 57-60 | GPIO pin environment mapping (PIR, green, red, buzzer) |
| /home/pi/Desktop/IOT/monitor.py | 123-142 | GPIO initialization sequence and pin setup |
| /home/pi/Desktop/IOT/monitor.py | 272-319 | Motion read + LED/buzzer control and timing patterns |
| /home/pi/Desktop/IOT/monitor.py | 517-556 | PIR-triggered scan window state logic in main run loop |
| /home/pi/Desktop/IOT/monitor.py | 572-587 | GPIO and output cleanup on shutdown |
| /home/pi/Desktop/IOT/iot_app/services/gpio_service.py | 1-93 | GPIO abstraction, mock fallback, pin I/O helpers |
| /home/pi/Desktop/IOT/iot_app/config.py | 19-24, 40-43 | GPIO pin config model and defaults |
| /home/pi/Desktop/IOT/iot_app/state.py | 4-16, 22-35 | Runtime hardware state fields and snapshot exposure |

### Hardware Owned
| Component | GPIO Pin | Purpose |
|-----------|----------|---------|
| PIR motion sensor | 23 | Triggers 20-second active recognition window |
| Green LED | 17 | Indicates recognised person event |
| Red LED | 27 | Indicates unknown/intrusion event |
| Buzzer | 22 | Audible unknown/intrusion alert |

### APIs & Services Used
- `RPi.GPIO`: Direct hardware I/O control for PIR, LEDs, and buzzer.
- Internal runtime state service (`RuntimeState`): shares GPIO/camera readiness and errors with web APIs.

### Live Demo Steps
1. Start the system with `./start.sh`.
2. Show baseline status where PIR is in standby.
3. Move hand in front of PIR to trigger motion.
4. Show countdown begins at 20 seconds and scan window stays active.
5. Trigger unknown path and show red LED + buzzer behavior.
6. Trigger recognised path and show green LED behavior.
7. Stop process with Ctrl+C and show safe hardware cleanup.

### Viva Questions & Answers
Q1: Why do we use BCM pin numbering in this project?
A1: BCM numbering maps to Raspberry Pi GPIO IDs used by software, making pin configuration consistent across scripts and deployment.

Q2: What happens if `RPi.GPIO` is unavailable?
A2: The code switches to soft mode or mock behavior so the app continues without crashing, which is useful for development/testing environments.

Q3: How is the 20-second scan window implemented?
A3: On motion, `scan_active_until` is set to current monotonic time plus `SCAN_WINDOW_SECONDS`, then checked each loop iteration.

Q4: Why is monotonic time used for scan logic?
A4: `time.monotonic()` avoids issues from system clock changes and gives stable elapsed-time calculations.

Q5: How are false stuck outputs prevented on shutdown?
A5: Cleanup explicitly sets outputs low and runs `GPIO.cleanup()` to release hardware state.

### Dependencies on Other Roles
Depends on Role 2 for camera frames during active windows, Role 3 for recognition outputs that choose green/red paths, and Role 6 for exposing hardware state on dashboard.

---

## ROLE 2 — Camera & Stream Pipeline
### Assigned To
Person A | Person B

### Overview
This role ensures reliable camera capture and end-to-end frame delivery to users. They manage camera initialization, frame conversion, raw/annotated frame persistence in `/tmp`, and MJPEG streaming through Flask routes. Their success criteria is uninterrupted live feed and graceful fallback when camera data is unavailable.

### Files & Line Ownership
| File | Lines | Responsibility |
|------|-------|----------------|
| /home/pi/Desktop/IOT/monitor.py | 42-45 | Picamera2 import gating |
| /home/pi/Desktop/IOT/monitor.py | 64-66 | Frame dimension and capture loop timing config |
| /home/pi/Desktop/IOT/monitor.py | 145-161 | Picamera2 startup and stream configuration |
| /home/pi/Desktop/IOT/monitor.py | 213-221 | JPEG encoding and atomic frame writes |
| /home/pi/Desktop/IOT/monitor.py | 259-270 | Runtime frame capture + RGB/BGR conversion |
| /home/pi/Desktop/IOT/monitor.py | 558-570 | Raw and annotated frame update flow |
| /home/pi/Desktop/IOT/iot_app/services/camera_service.py | 1-69 | Service-level camera init/capture/retry/stop |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 89-115 | Cached frame generator and multipart streaming |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 157-159 | `/video_feed` endpoint serving MJPEG stream |
| /home/pi/Desktop/IOT/app.py | 1-8 | Flask runtime entrypoint for stream-serving app |

### Hardware Owned
| Component | GPIO Pin | Purpose |
|-----------|----------|---------|
| Raspberry Pi Camera Module | N/A (CSI bus) | Captures RGB frames at configured resolution |
| CSI ribbon connection | N/A | Physical data path between camera and Pi |
| Raspberry Pi board | N/A | Runs capture daemon and Flask stream endpoint |

### APIs & Services Used
- `Picamera2` / `libcamera`: low-level camera device access.
- Flask `Response` with multipart boundary: browser-consumable MJPEG streaming.
- OpenCV (`cv2`): color conversion and JPEG encoding.

### Live Demo Steps
1. Start project and verify monitor logs include `Picamera2 started`.
2. Open dashboard URL and confirm live image updates.
3. Show `/tmp/iot_latest_raw.jpg` timestamp changes over time.
4. Show `/tmp/iot_latest_annotated.jpg` updates during active scans.
5. Disconnect/disable camera briefly (or simulate failure) and show graceful fallback frame behavior.

### Viva Questions & Answers
Q1: Why is camera ownership centralized in `monitor.py`?
A1: A single owner prevents hardware lock conflicts that happen when Flask and daemon both open the camera.

Q2: Why do we convert RGB to BGR?
A2: Picamera outputs RGB arrays, while OpenCV processing/encoding path expects BGR by default.

Q3: Why write frames to `/tmp` instead of in-memory sockets?
A3: `/tmp` files decouple producer and consumer processes, simplifying resilience and process restarts.

Q4: What is the purpose of cached-frame streaming logic?
A4: It avoids re-reading unchanged files every iteration and serves the last valid frame smoothly.

Q5: How is stream corruption reduced during writes?
A5: Frames are written to temp files and atomically replaced, so readers don’t consume partial JPEGs.

### Dependencies on Other Roles
Depends on Role 1 for motion windows, Role 3 for annotations, and Role 6 for dashboard presentation of the stream.

---

## ROLE 3 — Face Recognition & Enrollment
### Assigned To
Person A | Person B

### Overview
This role owns identity logic: loading known faces, matching live encodings, and managing enrollment from the dashboard. They ensure recognised/unknown decisions are accurate enough for the hardware and alert stack. They also maintain known-face dataset quality and explain why some source images are rejected.

### Files & Line Ownership
| File | Lines | Responsibility |
|------|-------|----------------|
| /home/pi/Desktop/IOT/monitor.py | 230-257 | Known face loading from nested `known_faces` tree |
| /home/pi/Desktop/IOT/monitor.py | 394-511 | Face detection, matching, confidence, annotation labels |
| /home/pi/Desktop/IOT/monitor.py | 513-516 | Hot reload trigger handling for face updates |
| /home/pi/Desktop/IOT/iot_app/services/face_recognition_service.py | 1-101 | Service-level encoding load, recognize, summarize |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 117-123 | Enrollment filename/version helper |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 211-242 | `/enroll` API flow, face check, save, reload signal |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 245-247 | Enrolled user listing API |
| /home/pi/Desktop/IOT/README.md | 11-18, 24-26 | Feature-level recognition/enrollment definitions |

### Hardware Owned
| Component | GPIO Pin | Purpose |
|-----------|----------|---------|
| Pi Camera Module | N/A | Captures face images for enrollment/recognition |
| Presentation positioning stand/tripod | N/A | Keeps consistent angle/distance for reliable encoding |

### APIs & Services Used
- `face_recognition` (dlib backend): face locations, encodings, compare, distance.
- OpenCV: frame conversion and saved enrollment image generation.
- Local filesystem under `known_faces`: source-of-truth identity dataset.

### Live Demo Steps
1. Open dashboard and enter a new person name.
2. Click `Capture & Enroll` with clear front-facing pose.
3. Show success message and new user in enrolled list.
4. Trigger motion and present the enrolled face.
5. Show `RECOGNISED` state and confidence update.
6. Present non-enrolled face and show `UNKNOWN` state.

### Viva Questions & Answers
Q1: Why can enrollment fail with "No face detected"?
A1: The source frame may be blurred, occluded, poorly lit, or not front-facing enough for the detector.

Q2: How is best match selected among known faces?
A2: The code checks tolerance matches and uses the minimum distance index from `face_distance`.

Q3: What controls strictness of recognition?
A3: `FACE_TOLERANCE` in environment/config; lower values are stricter, higher values are more permissive.

Q4: Why is upsample used in detection?
A4: Upsample increases detection sensitivity for smaller/farther faces in surveillance scenarios.

Q5: How does enrollment become active in daemon without restart?
A5: Route writes reload flag and daemon reloads encodings when it detects that flag.

### Dependencies on Other Roles
Depends on Role 2 for valid camera frames, Role 1 for motion windows, and Role 6 for enrollment UI interactions.

---

## ROLE 4 — Firebase + Cloud Functions
### Assigned To
Person A | Person B

### Overview
This role handles all event persistence and cloud-side post-processing. They own Firebase initialization, writing recognition payloads, reading historical events for APIs, and maintaining Cloud Function logic that processes uploaded frames into structured recognition metadata. They demonstrate that local detections are traceable in cloud records.

### Files & Line Ownership
| File | Lines | Responsibility |
|------|-------|----------------|
| /home/pi/Desktop/IOT/monitor.py | 31-35 | Firebase SDK import and availability guard |
| /home/pi/Desktop/IOT/monitor.py | 52-53 | Firebase env settings |
| /home/pi/Desktop/IOT/monitor.py | 163-183 | Firebase RTDB initialization and app reuse |
| /home/pi/Desktop/IOT/monitor.py | 365-374 | Per-event payload write to RTDB |
| /home/pi/Desktop/IOT/monitor.py | 486-504 | Event payload schema fields written by daemon |
| /home/pi/Desktop/IOT/iot_app/services/firebase_service.py | 1-47 | Firestore service init and event logging |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 71-87 | RTDB app caching and lazy initialization |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 169-180 | `/api/recognitions` retrieval and sorting |
| /home/pi/Desktop/IOT/cloud-functions/functions/index.js | 1-119 | Storage trigger, Vision annotate, RTDB write pipeline |

### Hardware Owned
| Component | GPIO Pin | Purpose |
|-----------|----------|---------|
| Raspberry Pi device (event producer) | N/A | Sends local recognition payloads to cloud |
| Camera snapshot source | N/A | Produces image artifacts for cloud function analysis |

### APIs & Services Used
- Firebase Realtime Database (`firebase_admin.db`): structured event persistence and retrieval.
- Firebase Firestore (`firestore.client()`): additional event logging service path.
- Firebase Cloud Functions v2 (`onObjectFinalized`): serverless frame-analysis trigger.
- Firebase Storage event metadata: context for cloud inference.

### Live Demo Steps
1. Trigger a scan event from PIR or manual scan.
2. Open `/api/recognitions?device=pi-cam-01` and show newest event appears.
3. Show key payload fields (`name`, `status`, `confidence`, `timestamp_ms`).
4. Upload a frame to `frames/<device>/<frame>.jpg` path (or trigger existing upload flow).
5. Show Cloud Function writes structured object/labels/faces under `recognitions/<device>/<frameId>`.

### Viva Questions & Answers
Q1: Why use RTDB for recognition timeline?
A1: RTDB provides simple key-based hierarchical writes and quick retrieval for recent event lists.

Q2: What does Cloud Function trigger on?
A2: It triggers on finalized Storage objects and only processes image files under `frames/` path.

Q3: Why keep both local daemon write and cloud function path?
A3: Local write provides immediate event availability; cloud function enriches data asynchronously from stored images.

Q4: How are duplicate Firebase app init issues avoided?
A4: Code checks named app cache and reuses existing app handles before initializing a new one.

Q5: What causes `/api/recognitions` to return 503?
A5: Connection/read errors against RTDB app or missing credentials/database availability.

### Dependencies on Other Roles
Depends on Role 2/3 for event generation and image sources, and Role 6 for dashboard visualization of retrieved records.

---

## ROLE 5 — Telegram Bot + Vision API
### Assigned To
Person A | Person B

### Overview
This role owns external intelligence and notification delivery. They manage Vision API label extraction from active frames and Telegram bot alert delivery with image and contextual caption. They validate that unknown and recognised events produce understandable, timestamped mobile notifications.

### Files & Line Ownership
| File | Lines | Responsibility |
|------|-------|----------------|
| /home/pi/Desktop/IOT/monitor.py | 37-40 | Vision API import and availability guard |
| /home/pi/Desktop/IOT/monitor.py | 48, 54-55 | Device and Telegram environment identity |
| /home/pi/Desktop/IOT/monitor.py | 185-195 | Vision client initialization |
| /home/pi/Desktop/IOT/monitor.py | 197-206 | Telegram bot initialization |
| /home/pi/Desktop/IOT/monitor.py | 320-342 | Alert caption templates for recognised/unknown events |
| /home/pi/Desktop/IOT/monitor.py | 344-362 | Async Telegram photo send wrapper |
| /home/pi/Desktop/IOT/monitor.py | 364-389 | Vision label extraction per frame |
| /home/pi/Desktop/IOT/monitor.py | 469-481 | Triggering recognized/unknown local + Telegram alert path |
| /home/pi/Desktop/IOT/iot_app/services/telegram_service.py | 1-31 | Reusable Telegram service class |
| /home/pi/Desktop/IOT/requirements.txt | 7-9 | Vision/Telegram/request dependencies |
| /home/pi/Desktop/IOT/README.md | 103-129 | Vision direct client and related setup guidance |

### Hardware Owned
| Component | GPIO Pin | Purpose |
|-----------|----------|---------|
| Pi Camera Module | N/A | Captures images attached to Telegram alerts |
| Red LED + buzzer context | 27, 22 | Physical escalation synchronized with UNKNOWN alerts |

### APIs & Services Used
- Google Cloud Vision API (`ImageAnnotatorClient.label_detection`): top labels for contextual awareness.
- Telegram Bot API (`send_photo`): mobile push notification with image + caption.
- Python asyncio runtime: executes async bot call from synchronous daemon flow.

### Live Demo Steps
1. Confirm Vision and Telegram are configured in startup logs.
2. Trigger an unknown event in front of camera.
3. Show dashboard marks unknown and alert path executes.
4. Show Telegram message with photo and warning caption.
5. Trigger recognised event and show different caption content and confidence.

### Viva Questions & Answers
Q1: Why use Telegram photo alerts instead of text-only alerts?
A1: Photo evidence provides immediate visual verification and reduces ambiguity.

Q2: What labels are returned from Vision API?
A2: Up to 10 top label descriptions from the current frame, used for scene context.

Q3: What if Telegram token/chat ID is missing?
A3: Bot is marked unavailable; detection continues and events are still logged locally/cloud-side.

Q4: Why wrap Telegram send in `asyncio.run`?
A4: Telegram client method is async; wrapper allows invocation from synchronous daemon processing.

Q5: Can Vision API failure break surveillance loop?
A5: No, failures are caught and labels fall back to empty list so core detection keeps running.

### Dependencies on Other Roles
Depends on Role 2 for frame capture, Role 3 for recognition status, and Role 4 for cloud event visibility alignment.

---

## ROLE 6 — Dashboard UX + Deployment
### Assigned To
Person A | Person B

### Overview
This role owns user-facing interaction and project run/deploy quality. They maintain dashboard structure, polling behavior, enrollment UX messages, and route wiring that serves statuses and events. They also own startup command flow, dependency declarations, and presentation-ready runbook/troubleshooting.

### Files & Line Ownership
| File | Lines | Responsibility |
|------|-------|----------------|
| /home/pi/Desktop/IOT/dashboard.html | 1-310 | UI structure and CSS visual system |
| /home/pi/Desktop/IOT/dashboard.html | 312-364 | Hero, status cards, feed, verification and enrollment panels |
| /home/pi/Desktop/IOT/dashboard.html | 386-581 | JS polling, rendering, enrollment and scan-now interactions |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 48-69 | Default status model and status-file merge helpers |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 149-166 | `/`, `/dashboard`, `/video_feed`, `/api/status` endpoints |
| /home/pi/Desktop/IOT/iot_app/web/routes.py | 189-208 | camera status + manual scan API endpoints |
| /home/pi/Desktop/IOT/iot_app/__init__.py | 1-28 | Flask app factory and blueprint wiring |
| /home/pi/Desktop/IOT/app.py | 1-8 | Flask process entrypoint |
| /home/pi/Desktop/IOT/start.sh | 1-9 | Single-command startup sequence |
| /home/pi/Desktop/IOT/requirements.txt | 1-9 | Runtime dependency manifest |
| /home/pi/Desktop/IOT/README.md | 1-172 | Setup, usage, deployment and cloud task docs |

### Hardware Owned
| Component | GPIO Pin | Purpose |
|-----------|----------|---------|
| Raspberry Pi host | N/A | Runs Flask + monitor startup workflow |
| Client laptop/phone browser | N/A | Displays dashboard and validates responsive UX |

### APIs & Services Used
- Flask routes + JSON APIs: serve status, events, enrollment, and stream endpoints.
- Browser Fetch API: periodic polling to keep dashboard real-time.
- Linux shell startup (`start.sh`): process orchestration.

### Live Demo Steps
1. Run `cd /home/pi/Desktop/IOT && ./start.sh`.
2. Open `http://<pi-ip>:5000/dashboard`.
3. Explain each status card and live update behavior.
4. Use `Scan Now` and show status transition on dashboard.
5. Use `Capture & Enroll`, then refresh enrolled users list.
6. Open alerts log and show newest detection rows update automatically.

### Viva Questions & Answers
Q1: Why poll `/api/status` every 1 second but `/api/recognitions` every 3 seconds?
A1: Status needs near-real-time responsiveness; recognition history can update slightly slower to reduce backend load.

Q2: Why does `/dashboard` read a static HTML file instead of Jinja template rendering?
A2: The architecture uses a standalone dashboard page with client-side fetch logic for simpler decoupling.

Q3: What command starts everything for demo day?
A3: `cd /home/pi/Desktop/IOT && ./start.sh`.

Q4: What indicates degraded service on dashboard?
A4: `firebase` disconnected, `vision_api` inactive, missing live frame, or status/event API failures.

Q5: How is process initialization order handled?
A5: `start.sh` starts Flask first, waits briefly, then launches monitor daemon for hardware/stream pipeline.

### Dependencies on Other Roles
Depends on Role 1 for accurate hardware status, Role 2 for feed availability, Role 3 for enrollment outputs, Role 4 for event history, and Role 5 for alert metadata fields.

---

## How To Run The Project
Use this single command:

```bash
cd /home/pi/Desktop/IOT && ./start.sh
```

## Troubleshooting Quick Reference
1. Camera feed blank
- Symptom: `/video_feed` shows placeholder or no frame updates.
- Fix: Verify Picamera2/libcamera availability and confirm monitor logs include `[CAMERA] Picamera2 started`.

2. GPIO not responding (LED/buzzer/PIR)
- Symptom: No physical response during scans.
- Fix: Check BCM wiring for pins 23/17/27/22 and run under environment with `RPi.GPIO` access.

3. Enrollment fails with "No face detected"
- Symptom: `/enroll` returns 422.
- Fix: Improve lighting, face orientation, and distance; ensure live raw frame exists at `/tmp/iot_latest_raw.jpg`.

4. Firebase events not appearing
- Symptom: `/api/recognitions` empty/disconnected.
- Fix: Validate `FIREBASE_DB_URL` and `GOOGLE_APPLICATION_CREDENTIALS` path and service account permissions.

5. Telegram alerts not delivered
- Symptom: Unknown/recognized events occur but no mobile alert.
- Fix: Confirm `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set and bot has permission to message the chat.
