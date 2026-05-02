#!/bin/bash
cd /home/pi/Desktop/IOT
set -a && . .env.example && set +a
echo "Starting AI Surveillance System..."
echo "Loading known faces..."
/home/pi/Desktop/IOT/.venv/bin/python app.py &
sleep 3
/home/pi/Desktop/IOT/.venv/bin/python monitor.py &
echo "System started. Dashboard at http://$(hostname -I | cut -d' ' -f1):5000/dashboard"
