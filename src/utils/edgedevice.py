import tflite_runtime.interpreter as tflite
import logging
import os
import subprocess

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
    libedgetpu_path = "/BASE/dev_inference/libedgetpu.so.1"
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