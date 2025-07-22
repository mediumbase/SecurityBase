Security Camera Web Application
Description
A Flask-based web application for real-time video streaming, motion detection, snapshot capture, and time-lapse recording using a webcam. Features include Telegram notifications, night vision mode, camera parameter adjustments, and log management.
Features

Live Video Feed: Stream webcam footage in real-time.
Motion Detection: Automatically captures snapshots on motion with Telegram notifications.
Time-Lapse Recording: Schedule and capture time-lapse sequences.
Snapshot Management: View, download, and clear saved snapshots.
Camera Controls: Adjust resolution, FPS, brightness, contrast, and more.
Night Vision: Optimize settings for low-light conditions.
Logging: Monitor application activity via logs.
RESTful API: Control camera settings and retrieve metadata programmatically.

Requirements

Python 3.8+
Webcam (compatible with OpenCV)
Dependencies: flask, python-dotenv, opencv-python, pyav, numpy
Telegram bot token (for notifications, optional)
v4l2-ctl for camera control (Linux)

Installation

Clone the repository:git clone <repository-url>
cd <repository-directory>


Create and activate a virtual environment:python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


Install dependencies:pip install -r requirements.txt


Create a .env file in the root directory with:SNAPSHOT_DIR=media/snapshots
CAMERA_INDEX=0
CAMERA_WIDTH=640
CAMERA_HEIGHT=480
MOTION_THRESHOLD=25
MIN_MOTION_AREA=500
JPEG_QUALITY=95
FPS=30
NIGHT_VISION_BRIGHTNESS=50
NIGHT_VISION_CONTRAST=5
NIGHT_VISION_SATURATION=30
NIGHT_VISION_GAMMA=200
NIGHT_VISION_WHITE_BALANCE_AUTOMATIC=0
NIGHT_VISION_WHITE_BALANCE_TEMPERATURE=5000
NIGHT_VISION_AUTO_EXPOSURE=1
NIGHT_VISION_EXPOSURE_TIME_ABSOLUTE=500
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id


Ensure media/snapshots and logs directories are writable.

Usage

Run the application:python app.py


Access the web interface at http://localhost:5000.
Use API endpoints for advanced control (e.g., /camera_params, /start_time_lapse).

API Endpoints

GET /video_feed: Stream live video.
GET /snapshots: List paginated snapshots.
GET /snapshots/: Download a snapshot.
POST /clear_snapshots: Delete all snapshots.
POST /start_time_lapse: Start time-lapse with interval and number of images.
POST /stop_time_lapse: Stop time-lapse.
GET /logs: Retrieve recent logs.
GET/POST /camera_params: Get or update camera settings (resolution, FPS, motion thresholds).
POST /reset_camera_params: Reset camera to default settings.
POST /night_vision: Apply night vision settings.
GET /camera_metadata: Get camera metadata (resolution, frame rate, timestamp).
GET/POST /camera_controls: List or update camera controls (brightness, contrast, etc.).

Directory Structure

app.py: Main Flask application.
media/snapshots/: Stores captured snapshots.
logs/security_cam.log: Application logs.
src/utils/: Contains CameraManager and telegram_sender modules.
static/css/styles.css: Custom styles for the UI.
static/js/scripts.js: Client-side logic for snapshots, logs, and controls.
templates/index.html: Web interface.

Notes

Ensure the webcam is connected and accessible (/dev/video0 on Linux).
Motion detection sensitivity can be tuned via MOTION_THRESHOLD and MIN_MOTION_AREA in .env.
Time-lapse runs in a separate thread to avoid blocking the main application.
Night vision settings are defined in .env and applied via /night_vision.

Troubleshooting

Camera not detected: Verify webcam connection and driver installation.
Logs not generated: Check write permissions for logs/ directory.
Telegram errors: Validate bot token and chat ID in .env.
API errors: Review logs for detailed error messages.

License
MIT License