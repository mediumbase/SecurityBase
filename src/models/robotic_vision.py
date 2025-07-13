import logging
import cv2
import numpy as np
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class RoboticVision:
    """Manages fusion of text and object detections with heatmap visualization."""
    def __init__(self):
        self.priority_threshold = 0.8
        self.max_detections = 10

    def fuse_detections(self, text_detections: List[Dict], object_detections: List[Dict]) -> List[Dict]:
        """Combine text and object detections, prioritizing high-confidence targets.

        Args:
            text_detections: List of text detection dictionaries with label, confidence, and bbox.
            object_detections: List of object detection dictionaries with label, confidence, and bbox.

        Returns:
            List of fused detections with priority labels.
        """
        fused = []
        all_detections = text_detections + object_detections
        all_detections = sorted(all_detections, key=lambda x: x["confidence"], reverse=True)
        
        for detection in all_detections[:self.max_detections]:
            if detection["confidence"] >= self.priority_threshold:
                detection["priority"] = "high"
                logging.info(f"High-priority detection: {detection['label']} ({detection['confidence']:.2f}) at bbox {detection['bbox']}")
            else:
                detection["priority"] = "low"
            fused.append(detection)
        
        return fused

    def generate_heatmap(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """Generate a heatmap overlay for high-priority detections.

        Args:
            frame: Input frame to overlay heatmap on.
            detections: List of detections with priority and bbox.

        Returns:
            Frame with heatmap overlay.
        """
        heatmap = np.zeros_like(frame)
        h, w = frame.shape[:2]
        for detection in detections:
            if detection.get("priority") == "high" and "bbox" in detection:
                x1, y1, x2, y2 = detection["bbox"]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                if x2 > x1 and y2 > y1:
                    intensity = min(255, int(detection["confidence"] * 255))
                    cv2.rectangle(heatmap, (x1, y1), (x2, y2), (0, intensity, 0), -1)
        alpha = 0.4
        frame = cv2.addWeighted(frame, 1 - alpha, heatmap, alpha, 0)
        return frame