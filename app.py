from flask import Flask, render_template, jsonify, Response, request, send_from_directory
from dotenv import load_dotenv
import os
import logging
import threading
import time
import cv2
import numpy as np
from src.utils.camera import CameraManager
from src.models.object_detection import ObjectDetector
from src.models.text_detection import TextDetector
from src.models.robotic_vision import RoboticVision
from src.utils.telegram_sender import send_snapshot_to_telegram
from deep_sort_realtime.deepsort_tracker import DeepSort

load_dotenv()

app = Flask(__name__)

# Setup logging
os.makedirs("logs", exist_ok=True)
os.makedirs(os.path.expanduser(os.getenv("SNAPSHOT_DIR", "media/snapshots")), exist_ok=True)
app.logger.handlers.clear()
handler = logging.FileHandler("logs/security_cam.log")
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
app.logger.propagate = False

# Configuration
app.config.update({
    "SNAPSHOT_DIR": os.path.expanduser(os.getenv("SNAPSHOT_DIR", "media/snapshots")),
    "CAMERA_INDEX": int(os.getenv("CAMERA_INDEX", 0)),
    "CAMERA_WIDTH": int(os.getenv("CAMERA_WIDTH", 640)),
    "CAMERA_HEIGHT": int(os.getenv("CAMERA_HEIGHT", 480)),
    "MOTION_THRESHOLD": int(os.getenv("MOTION_THRESHOLD", 25)),
    "MIN_MOTION_AREA": int(os.getenv("MIN_MOTION_AREA", 500)),
    "JPEG_QUALITY": int(os.getenv("JPEG_QUALITY", 95)),
    "FPS": int(os.getenv("FPS", 30)),
    "USE_IR": os.getenv("USE_IR", "False").lower() == "true",
    "USE_KINECT": os.getenv("USE_KINECT", "False").lower() == "true"
})

# Validate Kinect-only requirement
if not app.config["USE_KINECT"]:
    app.logger.warning("USE_KINECT is not set to True in .env. This project requires Kinect-only operation.")

# Initialize components
camera_lock = threading.Lock()
detections_lock = threading.Lock()
camera_manager = CameraManager(
    camera_index=app.config["CAMERA_INDEX"],
    width=app.config["CAMERA_WIDTH"],
    height=app.config["CAMERA_HEIGHT"],
    motion_threshold=app.config["MOTION_THRESHOLD"],
    min_motion_area=app.config["MIN_MOTION_AREA"],
    snapshot_dir=app.config["SNAPSHOT_DIR"]
)

# Initialize DeepSort tracker
deepsort = DeepSort(max_age=30, nn_budget=None, embedder="mobilenet", half=False, bgr=True)

# Initialize detectors
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")  # Updated to point to local models directory
MODEL_MAP = {
    "objects": {
        "model": "efficientdet_lite0_320_ptq.tflite",
        "labels": "coco_labels.txt",
        "is_ssd": True
    },
    "plants": {
        "model": "mobilenet_v2_1.0_224_inat_plant_quant.tflite",
        "labels": "inat_plant_labels.txt",
        "is_ssd": False
    },
    "bugs": {
        "model": "mobilenet_v2_1.0_224_inat_insect_quant.tflite",
        "labels": "inat_insect_labels.txt",
        "is_ssd": False
    },
    "birds": {
        "model": "mobilenet_v2_1.0_224_inat_bird_quant.tflite",
        "labels": "inat_bird_labels.txt",
        "is_ssd": False
    },
    "faces": {
        "model": "ssd_mobilenet_v2_face_quant_postprocess.tflite",
        "labels": "face_labels.txt",
        "is_ssd": True
    },
    "traffic": {
        "model": "traffic_model.tflite",
        "labels": "traffic_labels.txt",
        "is_ssd": True
    }
}
detectors = {}
last_detections = []

for category, config in MODEL_MAP.items():
    model_path = os.path.join(MODEL_DIR, config["model"])
    label_path = os.path.join(MODEL_DIR, config["labels"])
    try:
        if os.path.exists(model_path) and os.path.exists(label_path):
            detectors[category] = ObjectDetector(model_path, label_path, config["is_ssd"])
            app.logger.info(f"Loaded {category} model: {model_path}")
        else:
            app.logger.error(f"Model or labels not found for {category}: {model_path}, {label_path}")
    except Exception as e:
        app.logger.error(f"Failed to load {category} model: {e}")

try:
    text_detector = TextDetector()
    app.logger.info("TextDetector initialized successfully")
except Exception as e:
    app.logger.error(f"Failed to initialize TextDetector: {e}")
    text_detector = None
robotic_vision = RoboticVision()

last_snapshot_time = 0

def save_snapshot(frame):
    global last_snapshot_time
    current_time = time.time()
    if current_time - last_snapshot_time >= 1:
        timestamp = time.strftime("%Y_%m%d_%I:%M%p").lower()
        filepath = os.path.join(app.config["SNAPSHOT_DIR"], f"snapshot_{timestamp}.jpg")
        cv2.imwrite(filepath, frame, [int(cv2.IMWRITE_JPEG_QUALITY), app.config["JPEG_QUALITY"]])
        app.logger.info(f"Snapshot saved: {filepath}")
        send_snapshot_to_telegram(filepath)
        last_snapshot_time = current_time
        return True
    return False

class TimeLapseController:
    def __init__(self, camera_manager):
        self.is_running = False
        self.thread = None
        self.lock = threading.Lock()
        self.camera_manager = camera_manager

    def capture_time_lapse(self, interval, num_images, mode, colormap):
        for i in range(num_images):
            if not self.is_running:
                break
            with camera_lock:
                frame = self.camera_manager.get_frame(mode=mode, colormap=colormap)
            if frame is not None:
                save_snapshot(frame)
            else:
                app.logger.error(f"Failed to capture time-lapse image {i + 1}/{num_images}")
            time.sleep(interval)
        self.is_running = False

    def start(self, interval, num_images, mode, colormap):
        with self.lock:
            if self.is_running:
                return False, "Time-lapse already running"
            self.is_running = True
            self.thread = threading.Thread(target=self.capture_time_lapse, args=(interval, num_images, mode, colormap))
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

def generate_frames(mode="rgb", colormap="JET", depth_object_detection=True, tracking_enabled=True):
    global last_detections
    frame_count = 0
    while True:
        with camera_lock:
            frame = camera_manager.get_frame(mode=mode, colormap=colormap)
        if frame is None:
            placeholder = np.zeros((app.config["CAMERA_HEIGHT"], app.config["CAMERA_WIDTH"], 3), dtype=np.uint8)
            cv2.putText(placeholder, "Kinect Offline", (50, app.config["CAMERA_HEIGHT"] // 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            ret, buffer = cv2.imencode(".jpg", placeholder, [int(cv2.IMWRITE_JPEG_QUALITY), app.config["JPEG_QUALITY"]])
        else:
            if camera_manager.detect_motion(frame):
                save_snapshot(frame)

            current_detections = []
            if detectors and (mode.lower() == "rgb" or (mode.lower() == "depth" and depth_object_detection)):
                frame_count += 1
                if frame_count % 3 == 0:
                    try:
                        object_detections = []
                        deepsort_detections = []
                        for category in detectors:
                            detections = detectors[category].detect(frame)
                            for d in detections:
                                d["category"] = category
                                object_detections.append(d)
                                if tracking_enabled and d["confidence"] > 0.5:
                                    x, y, w, h = d["bbox"]
                                    deepsort_detections.append(([x, y, w, h], d["confidence"], d["label"]))

                        # Update DeepSort tracker
                        if tracking_enabled and deepsort_detections:
                            tracks = deepsort.update_tracks(deepsort_detections, frame=frame)
                            for track in tracks:
                                if track.is_confirmed():
                                    x1, y1, x2, y2 = track.to_tlbr()
                                    track_id = track.track_id
                                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                                    cv2.putText(frame, f"ID: {track_id}", (int(x1), int(y1) - 10),
                                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                        text_detections = []
                        if mode.lower() == "rgb" and text_detector:
                            try:
                                text_detections = text_detector.detect_text(frame)
                                frame = text_detector.draw_text_boxes(frame, text_detections)
                                for detection in text_detections:
                                    detection["category"] = "text"
                                    detection["bbox"] = detection.get("bbox", [0, 0, frame.shape[1], frame.shape[0]])
                                app.logger.info(f"Text detections: {len(text_detections)} found")
                            except Exception as e:
                                app.logger.error(f"Text detection error: {e}")

                        fused_detections = robotic_vision.fuse_detections(text_detections, object_detections)
                        current_detections = fused_detections
                        with detections_lock:
                            last_detections.extend(fused_detections)
                            last_detections = last_detections[-robotic_vision.max_detections:]

                        frame = robotic_vision.generate_heatmap(frame, fused_detections)

                    except Exception as e:
                        app.logger.error(f"Detection processing error: {e}")

            ret, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), app.config["JPEG_QUALITY"]])
        if not ret:
            app.logger.error("Failed to encode frame")
            break
        yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    mode = request.args.get("mode", "rgb").lower()
    colormap = request.args.get("colormap", "JET").upper()
    depth_object_detection = request.args.get("depth_object_detection", "true").lower() == "true"
    tracking_enabled = request.args.get("tracking_enabled", "true").lower() == "true"
    app.logger.info(f"Starting video feed (mode: {mode}, colormap: {colormap}, depth_object_detection: {depth_object_detection})")
    return Response(generate_frames(mode, colormap, depth_object_detection, tracking_enabled), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/inference_data")
def inference_data():
    with detections_lock:
        return jsonify(last_detections[-5:])

@app.route("/plant_height")
def plant_height():
    try:
        with detections_lock:
            if last_detections:
                latest_detection = last_detections[-1]
                if latest_detection.get("category") == "plants" and "bbox" in latest_detection:
                    _, y1, _, y2 = latest_detection["bbox"]
                    height_pixels = y2 - y1
                    height_cm = height_pixels * 0.05  # Example scaling factor
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    return jsonify({
                        "height": height_cm,
                        "plant_name": latest_detection["label"],
                        "timestamp": timestamp
                    })
        return jsonify({
            "height": 0,
            "plant_name": "Unknown",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        app.logger.error(f"Error calculating plant height: {e}")
        return jsonify({
            "height": 0,
            "plant_name": "Unknown",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }), 500

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
            app.logger.info("All snapshots deleted")
            return jsonify({"message": "All snapshots deleted"}), 200
        return jsonify({"message": "No snapshots to delete"}), 200
    except Exception as e:
        app.logger.error(f"Error deleting snapshots: {e}")
        return jsonify({"message": f"Error deleting snapshots: {str(e)}"}), 500

@app.route("/start_time_lapse", methods=["POST"])
def start_time_lapse():
    data = request.get_json() or {}
    interval = float(data.get("interval", 60))
    num_images = int(data.get("num_images", 10))
    mode = data.get("mode", "rgb").lower()
    colormap = data.get("colormap", "JET").upper()
    if interval <= 0 or num_images <= 0:
        return jsonify({"error": "Invalid parameters"}), 400
    success, message = time_lapse_controller.start(interval, num_images, mode, colormap)
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
        app.logger.error(f"Error reading logs: {e}")
        return jsonify([f"Error reading logs: {str(e)}"])

@app.route("/camera_params", methods=["GET", "POST"])
def camera_params():
    if request.method == "POST":
        data = request.get_json() or {}
        with camera_lock:
            if "width" in data and "height" in data:
                app.config["CAMERA_WIDTH"] = int(data["width"])
                app.config["CAMERA_HEIGHT"] = int(data["height"])
            if "fps" in data:
                app.config["FPS"] = int(data["fps"])
            if "motion_threshold" in data:
                camera_manager.motion_threshold = int(data["motion_threshold"])
            if "min_motion_area" in data:
                camera_manager.min_motion_area = int(data["min_motion_area"])
        app.logger.info(f"Camera parameters updated: {data}")
        return jsonify({"message": "Parameters updated"}), 200
    return jsonify({
        "width": app.config["CAMERA_WIDTH"],
        "height": app.config["CAMERA_HEIGHT"],
        "fps": app.config["FPS"],
        "motion_threshold": camera_manager.motion_threshold,
        "min_motion_area": camera_manager.min_motion_area
    })

@app.route("/diagnostics")
def diagnostics():
    diagnostics = {
        "kinect_status": "active" if hasattr(camera_manager, "kinect_device") and camera_manager.kinect_device is not None else "inactive",
        "last_tilt_angle": camera_manager.last_tilt_angle if hasattr(camera_manager, "last_tilt_angle") else "unknown",
        "object_detection": "loaded" if detectors else "not loaded",
        "text_detection": "loaded" if text_detector else "not loaded",
        "last_snapshot_time": time.ctime(last_snapshot_time) if last_snapshot_time else "none",
        "models_loaded": list(detectors.keys())
    }
    suggestions = []
    if diagnostics["kinect_status"] == "inactive":
        suggestions.append("Check Kinect USB connection or try a different USB port. Ensure libfreenect is installed and permissions are set (sudo chmod -R 777 /dev/bus/usb).")
    if not detectors:
        suggestions.append("Verify TFLite model paths in models directory.")
    if not text_detector:
        suggestions.append("Verify pytesseract installation and Tesseract OCR binary.")
    return jsonify({"diagnostics": diagnostics, "suggestions": suggestions})

@app.route("/camera_controls", methods=["GET", "POST"])
def camera_controls():
    return jsonify({"error": "Camera controls not supported for Kinect"}), 400

@app.route("/set_tilt", methods=["POST"])
def set_tilt():
    data = request.get_json() or {}
    angle = data.get("angle", 0)
    if not isinstance(angle, (int, float)) or angle < -31 or angle > 31:
        return jsonify({"error": "Invalid tilt angle. Must be between -31 and 31."}), 400
    success = camera_manager.set_tilt(angle)
    if success:
        return jsonify({"message": f"Tilt set to {angle} degrees"}), 200
    return jsonify({"error": "Failed to set tilt. Kinect not initialized or freenect error."}), 500

@app.route("/get_tilt", methods=["GET"])
def get_tilt():
    angle = camera_manager.get_tilt()
    if angle is not None:
        return jsonify({"angle": angle}), 200
    return jsonify({"error": "Failed to get tilt angle. Kinect not initialized."}), 500

if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
    except KeyboardInterrupt:
        app.logger.info("Shutting down Flask app")
    finally:
        camera_manager.release()