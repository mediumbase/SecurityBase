import cv2
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ObjectDetector:
    def __init__(self):
        self.fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
        logging.info("ObjectDetector initialized")

    def validate_interpreters(self, interpreters, labels):
        if not interpreters or not labels:
            logging.warning("Empty interpreters or labels provided")
            return False
        for category in interpreters:
            if category not in labels or not labels[category]:
                logging.warning(f"Invalid labels for category: {category}")
                return False
        return True

    def generate_frames(self, camera, interpreters, labels, last_detections, max_retries=3):
        if not self.validate_interpreters(interpreters, labels):
            logging.warning("Streaming raw feed due to invalid interpreters/labels")
        else:
            logging.info(f"Interpreters loaded for: {list(interpreters.keys())}")

        if camera is None or not camera.isOpened():
            logging.error("Camera is None or not opened")
            return

        logging.info("Starting frame generation")
        retry_count = 0
        while retry_count < max_retries:
            try:
                success, frame = camera.read()
                if not success or frame is None:
                    logging.error("Failed to read valid frame from camera")
                    retry_count += 1
                    continue

                logging.debug(f"Frame shape: {frame.shape}")
                # Background subtraction
                fgmask = self.fgbg.apply(frame)
                _, fgmask = cv2.threshold(fgmask, 127, 255, cv2.THRESH_BINARY)
                contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    if cv2.contourArea(contour) > 500:
                        (x, y, w, h) = cv2.boundingRect(contour)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Object detection
                if interpreters:
                    for category, interpreter in interpreters.items():
                        try:
                            input_details = interpreter.get_input_details()
                            output_details = interpreter.get_output_details()
                            input_shape = input_details[0]['shape']

                            img = cv2.resize(frame, (input_shape[1], input_shape[2]))
                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            input_data = np.expand_dims(img_rgb, axis=0).astype(np.uint8)

                            interpreter.set_tensor(input_details[0]['index'], input_data)
                            interpreter.invoke()
                            output_data = interpreter.get_tensor(output_details[0]['index'])
                            predicted_label_idx = np.argmax(output_data[0])
                            confidence = output_data[0][predicted_label_idx]

                            if predicted_label_idx >= len(labels[category]):
                                logging.warning(f"Label index {predicted_label_idx} out of range for {category}")
                                continue

                            label = labels[category][predicted_label_idx].strip()
                            last_detections.append({
                                "category": category,
                                "label": label,
                                "confidence": float(confidence)
                            })

                            text_y = 30 + 40 * list(interpreters.keys()).index(category)
                            cv2.putText(frame, f"{category.upper()}: {label} ({confidence:.2f})",
                                        (10, text_y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        except Exception as e:
                            logging.error(f"Error in {category} detection: {e}")

                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                if not ret:
                    logging.warning("Failed to encode frame")
                    continue
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                retry_count = 0  # Reset on success
            except Exception as e:
                logging.error(f"Frame generation error: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    break
                time.sleep(1)

        logging.info("Frame generation stopped")

    def release(self):
        self.fgbg = None
        logging.info("ObjectDetector resources released")