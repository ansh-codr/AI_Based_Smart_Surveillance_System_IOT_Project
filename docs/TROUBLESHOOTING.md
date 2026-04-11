# Troubleshooting

## pip says externally managed
Use a venv and install inside it, or use system packages via apt on Raspberry Pi.

## Picamera2 camera open fails
- Enable camera in `raspi-config`
- Verify with `libcamera-hello`
- Ensure no other process is using camera

## GPIO permission/setup errors
Run on Raspberry Pi OS with correct permissions and hardware wiring.
