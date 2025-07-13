import os
import cv2
import numpy as np
import logging
try:
    import freenect
except ImportError:
    freenect = None
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SNAPSHOT_DIR = "/BASE/dev_inference/dashboard/media/plant_snapshots"

def get_real_feed():
    """Capture an RGB frame from Kinect."""
    if not freenect:
        logging.error("libfreenect not installed")
        return None
    try:
        frame = freenect.sync_get_video()[0]
        if frame is None:
            logging.warning("No RGB frame from Kinect")
            return None
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    except Exception as e:
        logging.error(f"Error capturing RGB feed: {e}")
        return None

def get_stem_outline():
    """Generate a stem outline from Kinect depth data."""
    if not freenect:
        logging.error("libfreenect not installed")
        return None
    try:
        depth = freenect.sync_get_depth()[0]
        if depth is None:
            logging.warning("No depth frame from Kinect")
            return None
        # Normalize depth for visualization
        depth = cv2.convertScaleAbs(depth, alpha=0.05)
        # Apply edge detection for stem outline
        edges = cv2.Canny(depth, 50, 150)
        # Convert to BGR for display
        outline = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        return outline
    except Exception as e:
        logging.error(f"Error generating stem outline: {e}")
        return None

def generate_view3_image(idx):
    """Generate a timelapse image from snapshots."""
    snapshot_files = sorted(
        [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".jpg")],
        key=lambda x: os.path.getmtime(os.path.join(SNAPSHOT_DIR, x))
    )
    if not snapshot_files or idx < 0 or idx >= len(snapshot_files):
        logging.warning("No valid snapshot for View 3 image")
        return None
    try:
        img_path = os.path.join(SNAPSHOT_DIR, snapshot_files[idx])
        img = cv2.imread(img_path)
        if img is None:
            logging.error(f"Failed to load snapshot: {img_path}")
            return None
        return img
    except Exception as e:
        logging.error(f"Error generating View 3 image: {e}")
        return None

def get_snapshot_count():
    """Count the number of snapshots."""
    try:
        return len([f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".jpg")])
    except Exception as e:
        logging.error(f"Error counting snapshots: {e}")
        return 0

def capture_snapshot():
    """Capture a snapshot, estimate plant height, and save a .ply file."""
    if not freenect:
        logging.error("libfreenect not installed")
        return None, None, 0
    try:
        # Capture RGB and depth
        rgb = freenect.sync_get_video()[0]
        depth = freenect.sync_get_depth()[0]
        if rgb is None or depth is None:
            logging.warning("Failed to capture RGB or depth")
            return None, None, 0

        rgb = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        
        # Estimate plant height from depth
        # Assume plant is in center of image
        h, w = depth.shape
        center_depth = depth[h//4:h*3//4, w//4:w*3//4]
        valid_depth = center_depth[center_depth > 0]
        if valid_depth.size == 0:
            logging.warning("No valid depth data for height estimation")
            return None, None, 0
        
        # Convert depth to meters (Kinect depth is in mm)
        height_m = (np.max(valid_depth) - np.min(valid_depth)) / 1000.0
        
        # Generate stem points (simplified)
        stem_points = []
        for y in range(h//4, h*3//4):
            for x in range(w//4, w*3//4):
                if depth[y, x] > 0:
                    stem_points.append([x, y, depth[y, x] / 1000.0])
        
        # Save snapshot
        timestamp = datetime.now().strftime("%Y_%m%d_%H%M%S")
        snapshot_path = os.path.join(SNAPSHOT_DIR, f"snapshot_{timestamp}.jpg")
        cv2.imwrite(snapshot_path, rgb)
        logging.info(f"Saved snapshot: {snapshot_path}")
        
        # Save .ply file (simplified point cloud)
        ply_path = os.path.join(SNAPSHOT_DIR, f"snapshot_{timestamp}.ply")
        with open(ply_path, 'w') as f:
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {len(stem_points)}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("end_header\n")
            for point in stem_points:
                f.write(f"{point[0]} {point[1]} {point[2]}\n")
        logging.info(f"Saved .ply file: {ply_path}")
        
        return stem_points, ply_path, height_m
    except Exception as e:
        logging.error(f"Error capturing snapshot: {e}")
        return None, None, 0