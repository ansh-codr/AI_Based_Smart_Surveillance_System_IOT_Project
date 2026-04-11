# API Endpoints

## GET /
Returns dashboard page.

## GET /video
Streams multipart MJPEG feed.

## GET /status
Returns JSON status:
- intrusion_detected
- motion_detected
- camera_ready
- camera_error
- frame_error
- gpio_ready
- gpio_error
