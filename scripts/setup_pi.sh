#!/usr/bin/env bash
set -e

sudo apt update
sudo apt install -y python3-venv python3-full python3-opencv python3-picamera2 python3-rpi.gpio

python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install Flask==3.1.0

echo "Setup complete. Run: source .venv/bin/activate && python app.py"
