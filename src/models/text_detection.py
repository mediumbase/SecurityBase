import cv2
import numpy as np
import pytesseract
import imutils
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TextDetector:
    def __init__(self):
        self.min_confidence = 0.5  # Minimum confidence for text detection

    def detect_text(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect text in a frame and return bounding boxes with extracted text.
        Optimized for single-character detection (e.g., 'G').
        Returns a list of dictionaries containing text, confidence, and bounding box coordinates.
        """
        detections = []
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Apply GaussianBlur to reduce noise
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            # Adaptive thresholding for better contrast
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
            )
            # Dilate to connect text regions
            kernel = np.ones((3, 3), np.uint8)
            thresh = cv2.dilate(thresh, kernel, iterations=1)

            # Find contours
            cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = imutils.grab_contours(cnts)
            cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]  # Limit to top 5 contours

            for c in cnts:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)

                if len(approx) >= 4:  # Look for rectangular or near-rectangular shapes
                    (x, y, w, h) = cv2.boundingRect(approx)
                    if w > 30 and h > 30:  # Increased size filter for single letters
                        # Crop the region with padding
                        padding = 5
                        x1, y1 = max(0, x - padding), max(0, y - padding)
                        x2, y2 = min(gray.shape[1], x + w + padding), min(gray.shape[0], y + h + padding)
                        cropped = gray[y1:y2, x1:x2]
                        
                        # Preprocess for OCR
                        cropped = cv2.resize(cropped, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                        _, cropped = cv2.threshold(
                            cropped, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                        )
                        cropped = cv2.GaussianBlur(cropped, (3, 3), 0)

                        # Perform OCR with single-character mode
                        custom_config = r'--oem 3 --psm 10 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                        text = pytesseract.image_to_string(cropped, config=custom_config).strip()

                        if text:  # Allow single characters
                            detections.append({
                                "category": "text",
                                "label": text,
                                "confidence": 0.9,  # Placeholder confidence
                                "bbox": (x1, y1, x2, y2)
                            })
                            logging.info(f"Detected text: {text} at ({x1}, {y1}, {x2-x1}, {y2-y1})")
        except Exception as e:
            logging.error(f"Text detection error: {e}")
        return detections

    def draw_text_boxes(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """Draw bounding boxes and text labels on the frame."""
        for detection in detections:
            x1, y1, x2, y2 = detection["bbox"]
            label = detection["label"]
            confidence = detection["confidence"]
            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
            # Draw text
            cv2.putText(frame, f"{label} ({confidence:.2f})",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        return frame