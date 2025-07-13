import tflite_runtime.interpreter as tflite
import logging
import os
import subprocess
import numpy as np
import cv2

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def check_tpu():
    """Check if TPU is detected via lsusb."""
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, check=True)
        if "1a6e:089a" in result.stdout:
            logging.info("TPU detected (Global Unichip 1a6e:089a)")
            return True
        logging.warning("TPU not detected in lsusb")
        return False
    except Exception as e:
        logging.error(f"Error checking TPU: {e}")
        return False

def load_models(models):
    """
    Load TFLite models and their labels for object detection, with Edge TPU support.
    
    Args:
        models (dict): Dictionary of model categories with model_path, label_path, and is_ssd.
    
    Returns:
        tuple: (interpreters, labels)
    """
    interpreters = {}
    labels = {}
    libedgetpu_path = "/usr/lib/libedgetpu.so.1"  # Common system path
    tpu_available = check_tpu()

    for category, config in models.items():
        model_path = config["model_path"]
        label_path = config["label_path"]
        
        try:
            interpreter = None
            if "edgetpu" in model_path and os.path.exists(libedgetpu_path) and tpu_available:
                try:
                    delegate = tflite.load_delegate(libedgetpu_path)
                    interpreter = tflite.Interpreter(
                        model_path=model_path,
                        experimental_delegates=[delegate]
                    )
                    logging.info(f"Loaded {category} model with Edge TPU: {model_path}")
                except Exception as e:
                    logging.warning(f"Edge TPU failed for {category}: {e}. Falling back to CPU.")
                    interpreter = tflite.Interpreter(model_path=model_path)
                    logging.info(f"Loaded {category} model on CPU: {model_path}")
            else:
                interpreter = tflite.Interpreter(model_path=model_path)
                logging.info(f"Loaded {category} model on CPU: {model_path}")
            
            interpreter.allocate_tensors()
            interpreters[category] = interpreter
            
            with open(label_path, "r") as f:
                labels[category] = [line.strip() for line in f.readlines()]
            logging.info(f"Loaded labels for {category}: {label_path}")
            
        except Exception as e:
            logging.error(f"Failed to load model {category}: {e}")
            continue
    
    return interpreters, labels

class ObjectDetector:
    def __init__(self, model_path, label_path, is_ssd=False):
        """
        Initialize the ObjectDetector with a TFLite model and labels.
        
        Args:
            model_path (str): Path to the TFLite model file.
            label_path (str): Path to the label file.
            is_ssd (bool): Whether the model is an SSD model.
        """
        self.is_ssd = is_ssd
        self.model_path = model_path
        self.label_path = label_path
        self.interpreter = None
        self.labels = []
        self.input_details = None
        self.output_details = None
        
        # Load model and labels
        try:
            models = {"default": {"model_path": model_path, "label_path": label_path}}
            interpreters, labels_dict = load_models(models)
            self.interpreter = interpreters.get("default")
            self.labels = labels_dict.get("default", [])
            if not self.interpreter or not self.labels:
                raise ValueError("Failed to load model or labels")
            
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            logging.info(f"ObjectDetector initialized for {model_path}")
        except Exception as e:
            logging.error(f"Failed to initialize ObjectDetector for {model_path}: {e}")
            raise

    def preprocess_image(self, image):
        """
        Preprocess the input image to match model requirements.
        
        Args:
            image: Input image (numpy array).
        
        Returns:
            Preprocessed image (numpy array).
        """
        input_shape = self.input_details[0]["shape"]
        input_height, input_width = input_shape[1], input_shape[2]
        image_resized = cv2.resize(image, (input_width, input_height))
        
        # Handle input data type
        input_dtype = self.input_details[0]["dtype"]
        if input_dtype == np.uint8:
            input_image = image_resized
        else:
            input_image = image_resized.astype(np.float32) / 255.0
        
        # Add batch dimension
        input_image = np.expand_dims(input_image, axis=0)
        return input_image

    def detect(self, image):
        """
        Perform object detection on the input image.
        
        Args:
            image: Input image (numpy array).
        
        Returns:
            List of detections with bbox, label, and confidence.
        """
        try:
            input_image = self.preprocess_image(image)
            self.interpreter.set_tensor(self.input_details[0]["index"], input_image)
            self.interpreter.invoke()
            
            detections = []
            if self.is_ssd:
                # SSD model outputs: [boxes, classes, scores, num_detections]
                boxes = self.interpreter.get_tensor(self.output_details[0]["index"])[0]
                classes = self.interpreter.get_tensor(self.output_details[1]["index"])[0]
                scores = self.interpreter.get_tensor(self.output_details[2]["index"])[0]
                num_detections = int(self.interpreter.get_tensor(self.output_details[3]["index"])[0])
                
                for i in range(num_detections):
                    if scores[i] > 0.3:  # Confidence threshold
                        ymin, xmin, ymax, xmax = boxes[i]
                        h, w = image.shape[:2]
                        bbox = [
                            int(xmin * w),
                            int(ymin * h),
                            int((xmax - xmin) * w),
                            int((ymax - ymin) * h)
                        ]
                        label_idx = int(classes[i])
                        label = self.labels[label_idx] if label_idx < len(self.labels) else "Unknown"
                        detections.append({
                            "bbox": bbox,
                            "label": label,
                            "confidence": float(scores[i]),
                            "priority": "high" if scores[i] > 0.7 else "medium" if scores[i] > 0.5 else "low"
                        })
            else:
                # Non-SSD (e.g., MobileNet) outputs: [scores]
                scores = self.interpreter.get_tensor(self.output_details[0]["index"])[0]
                label_idx = np.argmax(scores)
                if scores[label_idx] > 0.3:  # Confidence threshold
                    detections.append({
                        "bbox": [0, 0, image.shape[1], image.shape[0]],  # Full image for non-SSD
                        "label": self.labels[label_idx] if label_idx < len(self.labels) else "Unknown",
                        "confidence": float(scores[label_idx]),
                        "priority": "high" if scores[label_idx] > 0.7 else "medium" if scores[label_idx] > 0.5 else "low"
                    })
            
            return detections
        except Exception as e:
            logging.error(f"Detection error: {e}")
            return []