import av
import logging
import numpy as np
import cv2
import os
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class CameraManager:
    def __init__(self, width=640, height=480, motion_threshold=25, min_motion_area=500, snapshot_dir="media/snapshots", device="/dev/video0"):
        self.width = width
        self.height = height
        self.motion_threshold = motion_threshold
        self.min_motion_area = min_motion_area
        self.snapshot_dir = snapshot_dir
        self.device = os.getenv("CAMERA_DEVICE", device)
        self.container = None
        self.stream = None
        self.prev_frame = None
        self.open_camera()
        logging.info(f"Initialized camera with PyAV: {self.width}x{self.height} @ 30 FPS")

    def open_camera(self, max_retries=3, retry_delay=1):
        for attempt in range(max_retries):
            try:
                self.container = av.open(self.device, options={"video_size": f"{self.width}x{self.height}", "framerate": "30"})
                self.stream = next(s for s in self.container.streams if s.type == "video")
                logging.info("Camera opened successfully with PyAV")
                frame = self.get_frame()
                logging.info(f"Initial frame: {'Success' if frame is not None else 'None'}")
                if frame is not None:
                    return
                logging.error("Failed to get initial frame")
            except Exception as e:
                logging.error(f"Attempt {attempt + 1}/{max_retries} to open camera failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        self.container = None
        logging.error("Failed to open camera after retries")

    def is_opened(self):
        return self.container is not None

    def _preprocess_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        return gray

    def get_frame(self):
        if not self.is_opened():
            self.open_camera()
            if not self.is_opened():
                return None
        try:
            for packet in self.container.decode(self.stream):
                frame = packet.to_ndarray(format="bgr24")
                gray = self._preprocess_frame(frame)
                if self.prev_frame is None:
                    self.prev_frame = gray
                    return frame
                frame_delta = cv2.absdiff(self.prev_frame, gray)
                thresh = cv2.threshold(frame_delta, self.motion_threshold, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    if cv2.contourArea(contour) >= self.min_motion_area:
                        (x, y, w, h) = cv2.boundingRect(contour)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                self.prev_frame = gray
                return frame
        except Exception as e:
            logging.error(f"Error reading frame: {e}")
            self.container = None
            return None

    def detect_motion(self, frame):
        if frame is None or self.prev_frame is None:
            return False
        gray = self._preprocess_frame(frame)
        frame_delta = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(frame_delta, self.motion_threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if cv2.contourArea(contour) >= self.min_motion_area:
                return True
        return False

    def update_resolution(self, width, height):
        self.width = width
        self.height = height
        if self.container:
            self.release()
            self.open_camera()

    def update_fps(self, fps):
        if self.container:
            self.release()
            self.open_camera()

    def release(self):
        if self.container:
            self.container.close()
            self.container = None
            self.prev_frame = None
            logging.info("Camera released")