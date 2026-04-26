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
