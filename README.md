# AI-Based Smart Surveillance System IOT Project

A modular, AI-powered smart surveillance system designed for Raspberry Pi. This system integrates hardware sensors, computer vision, and cloud synchronization to provide real-time security monitoring.

## 🚀 Overview

The system remains in a low-power "idle" state until motion is detected via a PIR sensor. Once activated, it uses AI-driven facial recognition to distinguish between authorized individuals and unknown intruders, triggering local alerts and logging data to the cloud.

## ✨ Features

### Currently Implemented
- **Intelligent Motion Detection**: Activates monitoring only when movement is sensed via PIR sensors to conserve system resources.
- **AI Face Recognition**: Real-time identification using `face_recognition` and OpenCV to detect authorized vs. unknown persons.
- **Automated Alerting**:
  - **Local**: GPIO-controlled LED status indicators (Red/Green) and an audible Buzzer.
  - **Snapshots**: Automatically captures and saves photos of intruders.
- **Cloud Integration**:
  - Real-time event logging to **Firebase Firestore**.
  - Synchronizes motion and recognition events for remote monitoring.
- **Web Interface**:
  - **Live Video Stream**: Remote MJPEG video feed accessible via browser.
  - **Remote Enrollment**: API endpoint to enroll new authorized faces via the camera.
- **Deployment Ready**: Includes a `systemd` unit file for automatic startup on boot.

## 🛠️ Tech Stack
- **Languages**: Python 3.x
- **Frameworks**: Flask (Web/API)
- **AI/CV**: OpenCV, Face Recognition (dlib), Picamera2
- **Hardware**: RPi.GPIO (PIR, LED, Buzzer)
- **Cloud**: Firebase (Firestore)

## 📋 Project Status

### What's Done
- [x] Modular service architecture (Camera, Detection, Firebase, GPIO).
- [x] Intelligent monitoring loop (Motion -> Face Detection -> Face Recognition).
- [x] Local hardware alert system (Buzzer/LEDs).
- [x] Multi-threaded web server for live streaming and management.
- [x] Firebase integration for remote event tracking.
- [x] Deployment scripts for Raspberry Pi.

### Next Steps / To-Do
- [ ] **Mobile App Integration**: Build a dedicated mobile dashboard for real-time notifications.
- [ ] **Cloud Storage for Images**: Upload intruder snapshots directly to Firebase Storage or S3.
- [ ] **Advanced Analytics**: Track frequency of visits and peak activity times.
- [ ] **Configuration UI**: A web-based settings panel to change GPIO pins and sensitivity without editing code.

## ⚙️ Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/ansh-codr/AI_Based_Smart_Surveillance_System_IOT_Project.git
   cd AI_Based_Smart_Surveillance_System_IOT_Project
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Config**: Setup your Firebase credentials and configure GPIO pins in `iot_app/config.py`.
4. **Run the application**:
   ```bash
   python app.py
   ```

## Google Vision Integration (Task 3-5)

### Task 3 - IoT Device Client via Firebase

This repo now includes a complete device script:
- `scripts/iot_firebase_frame_client.py`

What it does:
1. Captures one camera frame.
2. Uploads the image to Firebase Storage under `frames/<deviceId>/<frameId>.jpg`.
3. Polls Firebase Realtime Database at `recognitions/<deviceId>/<frameId>`.
4. Prints result and raises local alert message when a person is detected.

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install opencv-python requests
```

Copy and fill environment values:

```bash
cp .env.example .env
```

Values that must be replaced in `.env`:
- `<<<REPLACE_THIS_FIREBASE_WEB_API_KEY>>>`
- `<<<REPLACE_THIS_RTDB_URL>>>`
- `<<<REPLACE_THIS_STORAGE_BUCKET>>>`
- `<<<REPLACE_THIS_DEVICE_USER_EMAIL>>>`
- `<<<REPLACE_THIS_DEVICE_USER_PASSWORD>>>`
- `<<<REPLACE_THIS_DEVICE_ID>>>`

Run Task 3 script:

```bash
set -a && source .env && set +a
python scripts/iot_firebase_frame_client.py
```

### Task 4 - Direct Vision API Call (No Firebase Function)

This repo also includes a direct-call script:
- `scripts/direct_vision_client.py`

Install dependencies:

```bash
source .venv/bin/activate
pip install google-cloud-vision opencv-python
```

Set credential path:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="<<<REPLACE_THIS_ABSOLUTE_PATH_TO_SERVICE_ACCOUNT_JSON>>>"
```

Run Task 4 script:

```bash
python scripts/direct_vision_client.py
```

### Task 5 - Security and Rules

Security files added:
- `cloud-functions/storage.rules`
- `cloud-functions/database.rules.json`
- `.env.example`
- `.gitignore` (prevents accidental secret commits)

Deploy rules:

```bash
cd cloud-functions
firebase deploy --only storage,database
```

Deploy function:

```bash
cd cloud-functions/functions
npm install
npm run lint
firebase deploy --only functions:analyzeUploadedFrame
```

### Common Errors and Fixes

1. `401/403` on Storage upload
  - Confirm Email/Password auth enabled in Firebase Authentication.
  - Confirm device user credentials in `.env`.

2. No result appears in Realtime Database
  - Confirm Cloud Function deployed successfully.
  - Confirm image uploaded to `frames/<deviceId>/<frameId>.jpg`.
  - Confirm function region matches bucket region (`us-east1` here).

3. Vision permission errors
  - Ensure service account used by function has access to Vision API.
  - Ensure Vision API is enabled in the same GCP project.

4. Eventarc service-agent permission error during deploy
  - Wait a few minutes for IAM propagation, then redeploy.
  - Recheck IAM role grants for required service agents.
