#!/usr/bin/env python3
import cv2
import numpy as np
import freenect
import logging
import time
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class CameraManager:
    def __init__(self, camera_index=0, width=640, height=480, motion_threshold=25, min_motion_area=500, snapshot_dir="media/snapshots"):
        self.camera_index = camera_index  # Unused for Kinect, kept for compatibility
        self.width = width
        self.height = height
        self.motion_threshold = motion_threshold
        self.min_motion_area = min_motion_area
        self.snapshot_dir = snapshot_dir
        self.camera = None
        self.prev_frame = None
        self.use_kinect = True
        self.kinect_device = None
        self.last_tilt_angle = 0
        self.initialize_camera()

    def initialize_camera(self):
        """Initialize Kinect only; no USB camera fallback."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                depth, _ = freenect.sync_get_depth()
                rgb, _ = freenect.sync_get_video()
                if depth is not None and rgb is not None:
                    self.kinect_device = freenect.open_device(freenect.init(), 0)
                    logging.info("Kinect initialized successfully")
                    return
            except Exception as e:
                if "LIBUSB_ERROR_BUSY" in str(e):
                    logging.info(f"Ignoring LIBUSB_ERROR_BUSY (attempt {attempt + 1}/{max_attempts})")
                else:
                    logging.error(f"Kinect initialization failed (attempt {attempt + 1}/{max_attempts}): {e}")
                time.sleep(1)
        logging.error("Kinect initialization failed after all attempts")
        raise RuntimeError("Failed to initialize Kinect; this project requires Kinect-only operation")

    def set_tilt(self, angle):
        """Set Kinect tilt angle (-31 to +31 degrees)."""
        if not self.use_kinect or self.kinect_device is None:
            logging.error("Cannot set tilt: Kinect not initialized")
            return False
        try:
            angle = max(-31, min(31, angle))
            freenect.set_tilt_degs(self.kinect_device, angle)
            self.last_tilt_angle = angle
            logging.info(f"Kinect tilt set to {angle} degrees")
            return True
        except Exception as e:
            logging.error(f"Failed to set Kinect tilt: {e}")
            return False

    def get_tilt(self):
        """Get the current Kinect tilt angle."""
        if not self.use_kinect or self.kinect_device is None:
            logging.error("Cannot get tilt: Kinect not initialized")
            return None
        try:
            logging.info(f"Current Kinect tilt angle: {self.last_tilt_angle}")
            return self.last_tilt_angle
        except Exception as e:
            logging.error(f"Failed to get Kinect tilt: {e}")
            return None

    def get_depth(self, colormap="JET"):
        """Get depth frame from Kinect with specified colormap."""
        if not self.use_kinect:
            return None
        try:
            depth, _ = freenect.sync_get_depth()
            if depth is None:
                logging.error("Failed to get Kinect depth frame")
                return None
            depth = np.clip(depth, 0, 2**11 - 1)
            depth = (depth / (2**11 - 1) * 255).astype(np.uint8)
            colormap_map = {
                "JET": cv2.COLORMAP_JET,
                "HOT": cv2.COLORMAP_HOT,
                "RAINBOW": cv2.COLORMAP_RAINBOW,
                "BONE": cv2.COLORMAP_BONE,
                "NONE": None
            }
            if colormap_map.get(colormap) is not None:
                depth = cv2.applyColorMap(depth, colormap_map[colormap])
            else:
                depth = cv2.cvtColor(depth, cv2.COLOR_GRAY2BGR)
            return depth
        except Exception as e:
            logging.error(f"Kinect depth capture failed: {e}")
            return None

    def get_frame(self, mode="rgb", colormap="JET"):
        """Get a frame from Kinect with specified mode and colormap."""
        if not self.use_kinect:
            logging.error("Kinect not initialized")
            return None
        if mode.lower() == "depth":
            frame = self.get_depth(colormap=colormap)
            if frame is None:
                return None
        else:
            try:
                rgb, _ = freenect.sync_get_video()
                if rgb is None:
                    logging.error("Failed to get Kinect RGB frame")
                    return None
                frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            except Exception as e:
                logging.error(f"Kinect RGB capture failed: {e}")
                return None
        frame = cv2.resize(frame, (self.width, self.height))

        # Apply motion detection overlay
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        if self.prev_frame is not None:
            frame_delta = cv2.absdiff(self.prev_frame, gray)
            thresh = cv2.threshold(frame_delta, self.motion_threshold, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                if cv2.contourArea(contour) >= self.min_motion_area:
                    (x, y, w, h) = cv2.boundingRect(contour)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "Motion", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        self.prev_frame = gray
        return frame

    def detect_motion(self, frame):
        """Detect motion in the frame using background subtraction."""
        if frame is None or self.prev_frame is None:
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        frame_delta = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(frame_delta, self.motion_threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if cv2.contourArea(contour) >= self.min_motion_area:
                return True
        return False

    def release(self):
        """Release Kinect resources."""
        if self.use_kinect:
            try:
                if self.kinect_device is not None:
                    freenect.close_device(self.kinect_device)
                freenect.sync_stop()
                logging.info("Kinect stopped")
            except Exception as e:
                logging.error(f"Error stopping Kinect: {e}")
        self.camera = None
        self.kinect_device = None

    @staticmethod
    def diagnose_camera_issues():
        """Diagnose Kinect availability."""
        diagnostics = {}
        try:
            depth, _ = freenect.sync_get_depth()
            if depth is not None:
                diagnostics["Kinect"] = "Available"
            else:
                diagnostics["Kinect"] = "Not available"
        except Exception as e:
            diagnostics["Kinect"] = f"Not available: {str(e)}"
        return diagnostics