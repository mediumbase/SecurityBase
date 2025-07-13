from flask import Flask, render_template, jsonify, Response, request, send_from_directory
from dotenv import load_dotenv
import os
import logging
import threading
import time
import av
import numpy as np
import cv2
import subprocess
from src.utils.camera import CameraManager
from src.utils.telegram_sender import send_snapshot_to_telegram

load_dotenv()

app = Flask(__name__)

# Ensure directories exist
os.makedirs("logs", exist_ok=True)
os.makedirs("media/snapshots", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/security_cam.log"),
        logging.StreamHandler()
    ]
)

app.config.update({
    "SNAPSHOT_DIR": "media/snapshots",
    "CAMERA_WIDTH": int(os.getenv("CAMERA_WIDTH", 640)),
    "CAMERA_HEIGHT": int(os.getenv("CAMERA_HEIGHT", 480)),
    "MOTION_THRESHOLD": int(os.getenv("MOTION_THRESHOLD", 25)),
    "MIN_MOTION_AREA": int(os.getenv("MIN_MOTION_AREA", 500)),
    "JPEG_QUALITY": int(os.getenv("JPEG_QUALITY", 95)),
    "FPS": int(os.getenv("FPS", 30))
})

camera_lock = threading.Lock()
camera_manager = CameraManager(
    width=app.config["CAMERA_WIDTH"],
    height=app.config["CAMERA_HEIGHT"],
    motion_threshold=app.config["MOTION_THRESHOLD"],
    min_motion_area=app.config["MIN_MOTION_AREA"],
    snapshot_dir=app.config["SNAPSHOT_DIR"]
)

last_snapshot_time = 0

def save_snapshot(frame):
    global last_snapshot_time
    current_time = time.time()
    if current_time - last_snapshot_time >= 1:
        timestamp = time.strftime("%Y_%m%d_%I:%M%p").lower()
        filepath = os.path.join(app.config["SNAPSHOT_DIR"], f"snapshot_{timestamp}.jpg")
        success = cv2.imwrite(filepath, frame, [int(cv2.IMWRITE_JPEG_QUALITY), app.config["JPEG_QUALITY"]])
        if success:
            logging.info(f"Snapshot saved: {filepath}")
            send_snapshot_to_telegram(filepath)
            last_snapshot_time = current_time
            return True
        else:
            logging.error(f"Failed to save snapshot: {filepath}")
    return False

class TimeLapseController:
    def __init__(self, camera_manager):
        self.is_running = False
        self.thread = None
        self.lock = threading.Lock()
        self.camera_manager = camera_manager

    def capture_time_lapse(self, interval, num_images):
        for i in range(num_images):
            if not self.is_running:
                break
            frame = self.camera_manager.get_frame()
            if frame is not None:
                save_snapshot(frame)
            else:
                logging.error(f"Failed to capture time-lapse image {i + 1}/{num_images}")
            time.sleep(interval)
        self.is_running = False

    def start(self, interval, num_images):
        with self.lock:
            if self.is_running:
                return False, "Time-lapse already running"
            self.is_running = True
            self.thread = threading.Thread(target=self.capture_time_lapse, args=(interval, num_images))
            self.thread.daemon = True
            self.thread.start()
            return True, "Time-lapse started"

    def stop(self):
        with self.lock:
            if self.is_running:
                self.is_running = False
                self.thread.join()
                return True, "Time-lapse stopped"
            return False, "No time-lapse running"

time_lapse_controller = TimeLapseController(camera_manager)

def generate_frames():
    while True:
        with camera_lock:
            frame = camera_manager.get_frame()
        if frame is None:
            placeholder = np.zeros((app.config["CAMERA_HEIGHT"], app.config["CAMERA_WIDTH"], 3), dtype=np.uint8)
            cv2.putText(placeholder, "Camera Offline", (50, app.config["CAMERA_HEIGHT"] // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            ret, buffer = cv2.imencode(".jpg", placeholder, [int(cv2.IMWRITE_JPEG_QUALITY), app.config["JPEG_QUALITY"]])
        else:
            if camera_manager.detect_motion(frame):
                save_snapshot(frame)
            ret, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), app.config["JPEG_QUALITY"]])
        if not ret:
            logging.error("Failed to encode frame")
            break
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    logging.info("Starting video feed")
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/snapshots")
def list_snapshots():
    page = int(request.args.get("page", 1))
    per_page = 10
    snapshots = sorted(
        [f for f in os.listdir(app.config["SNAPSHOT_DIR"]) if f.endswith(".jpg")],
        reverse=True
    )
    total = len(snapshots)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_snapshots = snapshots[start:end]
    return jsonify({
        "snapshots": paginated_snapshots,
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_more": end < total
    })

@app.route("/snapshots/<filename>")
def serve_snapshot(filename):
    return send_from_directory(app.config["SNAPSHOT_DIR"], filename)

@app.route("/clear_snapshots", methods=["POST"])
def clear_snapshots():
    try:
        snapshot_dir = app.config["SNAPSHOT_DIR"]
        if os.path.exists(snapshot_dir):
            for file in os.listdir(snapshot_dir):
                if file.endswith(".jpg"):
                    os.remove(os.path.join(snapshot_dir, file))
            logging.info("All snapshots deleted")
            return jsonify({"message": "All snapshots deleted"}), 200
        return jsonify({"message": "No snapshots to delete"}), 200
    except Exception as e:
        logging.error(f"Error deleting snapshots: {e}")
        return jsonify({"message": f"Error deleting snapshots: {str(e)}"}), 500

@app.route("/start_time_lapse", methods=["POST"])
def start_time_lapse():
    data = request.get_json() or {}
    interval = float(data.get("interval", 60))
    num_images = int(data.get("num_images", 10))
    if interval <= 0 or num_images <= 0:
        return jsonify({"error": "Invalid parameters"}), 400
    success, message = time_lapse_controller.start(interval, num_images)
    return jsonify({"message": message}), 200 if success else 400

@app.route("/stop_time_lapse", methods=["POST"])
def stop_time_lapse():
    success, message = time_lapse_controller.stop()
    return jsonify({"message": message}), 200 if success else 400

@app.route("/logs")
def get_logs():
    log_file_path = "logs/security_cam.log"
    try:
        if not os.path.exists(log_file_path):
            with open(log_file_path, "w") as f:
                f.write("Log file initialized\n")
        with open(log_file_path, "r") as log_file:
            logs = log_file.readlines()[-10:]
        return jsonify([log.strip() for log in logs])
    except Exception as e:
        logging.error(f"Error reading logs: {e}")
        return jsonify([f"Error reading logs: {str(e)}"])

@app.route("/camera_params", methods=["GET", "POST"])
def camera_params():
    if request.method == "POST":
        data = request.get_json() or {}
        with camera_lock:
            if "resolution" in data:
                width, height = map(int, data["resolution"].split("x"))
                app.config["CAMERA_WIDTH"] = width
                app.config["CAMERA_HEIGHT"] = height
                camera_manager.update_resolution(width, height)
            if "fps" in data:
                app.config["FPS"] = int(data["fps"])
                camera_manager.update_fps(app.config["FPS"])
            if "motion_threshold" in data:
                camera_manager.motion_threshold = int(data["motion_threshold"])
                app.config["MOTION_THRESHOLD"] = int(data["motion_threshold"])
            if "min_motion_area" in data:
                camera_manager.min_motion_area = int(data["min_motion_area"])
                app.config["MIN_MOTION_AREA"] = int(data["min_motion_area"])
        logging.info(f"Camera parameters updated: {data}")
        return jsonify({"message": "Parameters updated"}), 200
    return jsonify({
        "resolution": f"{app.config['CAMERA_WIDTH']}x{app.config['CAMERA_HEIGHT']}",
        "fps": app.config["FPS"],
        "motion_threshold": camera_manager.motion_threshold,
        "min_motion_area": camera_manager.min_motion_area
    })

@app.route("/reset_camera_params", methods=["POST"])
def reset_camera_params():
    try:
        default_controls = {
            "brightness": 0,
            "contrast": 8,
            "saturation": 36,
            "hue": 10,
            "gamma": 125,
            "sharpness": 5,
            "backlight_compensation": 10,
            "white_balance_automatic": 1,
            "auto_exposure": 3,
            "focus_automatic_continuous": 1
        }
        with camera_lock:
            for control, value in default_controls.items():
                cmd = ['v4l2-ctl', '-d', '/dev/video0', '--set-ctrl', f'{control}={value}']
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                logging.debug(f"Reset {control}={value}: {result.stdout}")
            app.config["CAMERA_WIDTH"] = 640
            app.config["CAMERA_HEIGHT"] = 480
            app.config["FPS"] = 30
            app.config["MOTION_THRESHOLD"] = 25
            app.config["MIN_MOTION_AREA"] = 500
            camera_manager.update_resolution(640, 480)
            camera_manager.update_fps(30)
            camera_manager.motion_threshold = 25
            camera_manager.min_motion_area = 500
        logging.info("Camera parameters reset to defaults")
        return jsonify({"message": "Camera parameters reset to defaults"}), 200
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to reset camera parameters: {e.stderr}")
        return jsonify({"error": f"Failed to reset parameters: {e.stderr}"}), 500

@app.route("/night_vision", methods=["POST"])
def night_vision():
    try:
        night_settings = {
            "brightness": 50,
            "contrast": 5,
            "saturation": 30,
            "gamma": 200,
            "white_balance_automatic": 0,
            "white_balance_temperature": 5000,
            "auto_exposure": 1,
            "exposure_time_absolute": 500
        }
        with camera_lock:
            for control, value in night_settings.items():
                cmd = ['v4l2-ctl', '-d', '/dev/video0', '--set-ctrl', f'{control}={value}']
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                logging.debug(f"Set night vision {control}={value}: {result.stdout}")
        logging.info("Night vision settings applied")
        return jsonify({"message": "Night vision settings applied"}), 200
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to apply night vision settings: {e.stderr}")
        return jsonify({"error": f"Failed to apply night vision: {e.stderr}"}), 500

@app.route("/camera_metadata")
def camera_metadata():
    with camera_lock:
        if not camera_manager.is_opened():
            return jsonify({"error": "Camera not available"}), 503
        return jsonify({
            "resolution": f"{app.config['CAMERA_WIDTH']}x{app.config['CAMERA_HEIGHT']}",
            "timestamp": time.strftime("%Y-%m-%d %I:%M:%S %p"),
            "frame_rate": app.config["FPS"]
        })

@app.route("/camera_controls", methods=["GET", "POST"])
def camera_controls():
    if request.method == "POST":
        data = request.get_json() or {}
        try:
            for control, value in data.items():
                cmd = ['v4l2-ctl', '-d', '/dev/video0', '--set-ctrl', f'{control}={value}']
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                logging.debug(f"Set {control}={value}: {result.stdout}")
            logging.info(f"Camera controls updated: {data}")
            return jsonify({"message": "Camera controls updated"}), 200
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to set camera controls: {e.stderr}")
            return jsonify({"error": f"Failed to set controls: {e.stderr}"}), 500

    try:
        result = subprocess.run(['v4l2-ctl', '-d', '/dev/video0', '--list-ctrls'], capture_output=True, text=True, check=True)
        controls = []
        for line in result.stdout.splitlines():
            if 'int' in line or 'bool' in line:
                parts = line.split()
                name = parts[0]
                type_ = 'int' if 'int' in line else 'bool'
                min_ = max_ = step = default = value = ''
                for part in parts:
                    if part.startswith('min='):
                        min_ = part.split('=')[1]
                    elif part.startswith('max='):
                        max_ = part.split('=')[1]
                    elif part.startswith('step='):
                        step = part.split('=')[1]
                    elif part.startswith('default='):
                        default = part.split('=')[1]
                    elif part.startswith('value='):
                        value = part.split('=')[1]
                controls.append({
                    "name": name,
                    "type": type_,
                    "min": min_,
                    "max": max_,
                    "step": step,
                    "default": default,
                    "value": value,
                    "flags": ""
                })
        logging.debug(f"Listed camera controls: {controls}")
        return jsonify({"controls": controls})
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to list camera controls: {e.stderr}")
        return jsonify({"error": f"Failed to list controls: {e.stderr}"}), 500

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
    finally:
        camera_manager.release()